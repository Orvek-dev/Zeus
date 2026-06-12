from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from .context import echo_json, state_for_home

if TYPE_CHECKING:
    from zeus_agent.trust_loop_runtime import ParkedAction


def register_approval_commands(app: typer.Typer) -> None:
    @app.command("approve", help="Issue a graded standing grant, or resolve a parked ASK.")
    def approve(
        capability_id: str | None = typer.Argument(None, help="Capability to license, e.g. fs.write"),
        scope: str = typer.Option("auto", "--scope", help="auto | once | session | narrower"),
        session_id: str | None = typer.Option(None, "--session-id"),
        path: str | None = typer.Option(None, "--path", help="Narrowed path prefix (scope=narrower)."),
        hours: int = typer.Option(8, "--hours", help="Grant lifetime in hours (0 = no expiry)."),
        parked: str | None = typer.Option(None, "--parked", help="Resolve a parked ASK by parked_action_id."),
        last: bool = typer.Option(False, "--last", help="Resolve the newest pending parked ASK."),
        confirm: bool = typer.Option(False, "--confirm", help="Confirm an ambiguous newest-pending approval."),
        narrow_path: str | None = typer.Option(None, "--narrow-path", help="With --parked: approve only this path."),
        deny: bool = typer.Option(False, "--deny", help="With --parked: reject instead of approve."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.graded_approval_runtime import GrantScope, issue_grant

        if parked is not None and last:
            raise typer.BadParameter("use either --parked or --last, not both")
        if narrow_path is not None and parked is None and not last:
            raise typer.BadParameter("--narrow-path requires --parked or --last")
        if last and not deny and not confirm:
            raise typer.BadParameter("--last approval requires --confirm")
        if parked is not None or last:
            target = parked if parked is not None else _latest_pending_parked_id(home=home)
            _resolve_parked(target, deny=deny, confirm=confirm, narrow_path=narrow_path, home=home)
            return
        if capability_id is None:
            raise typer.BadParameter("provide a capability_id, or use --parked <id>")
        if scope == "auto":
            parsed_scope = GrantScope.narrower
            path = path if path is not None else str(Path.cwd())
        else:
            try:
                parsed_scope = GrantScope(scope)
            except ValueError:
                raise typer.BadParameter("scope must be auto, once, session, or narrower")
            if parsed_scope is GrantScope.narrower and path is None:
                path = str(Path.cwd())
        if parsed_scope is GrantScope.session and session_id is None:
            raise typer.BadParameter("--session-id is required for scope=session")
        grant = issue_grant(
            grant_id="grant.{0}.{1}".format(capability_id.replace(".", "_"), int(time.time())),
            capability_id=capability_id,
            scope=parsed_scope,
            session_id=session_id,
            narrowed_paths=(path,) if path is not None else (),
            expires_at_epoch=0 if hours <= 0 else int(time.time()) + hours * 3600,
        )
        state_for_home(home).add_grant(grant)
        echo_json(grant.model_dump(mode="json"))

    @app.command("approvals", help="List standing grants, or parked ASKs with --pending.")
    def approvals(
        pending: bool = typer.Option(False, "--pending", help="Show parked ASKs awaiting resolution."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        state = state_for_home(home)
        if pending:
            from zeus_agent.operator_inbox_runtime import pending_card
            from zeus_agent.trust_loop_runtime import SQLiteApprovalQueue, SQLiteControlPlaneStore

            queue = SQLiteApprovalQueue(SQLiteControlPlaneStore(state.state_path))
            rows = queue.pending(now=datetime.now(timezone.utc))
            payload = []
            for parked_item in rows:
                card = pending_card(parked_item)
                card["run_id"] = parked_item.action.run_id
                card["approval_effect"] = _approval_effect(parked_item)
                card["resolve"] = "zeus approve --parked {0}".format(parked_item.parked_action_id)
                payload.append(card)
            echo_json(payload)
            return
        echo_json([grant.model_dump(mode="json") for grant in state.load_grants().all()])

    @app.command("notify", help="POST pending approval cards to a webhook URL.")
    def notify(
        webhook: str = typer.Option(..., "--webhook", help="POST pending approval cards to this URL."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.operator_inbox_runtime import WebhookDeliveryError, deliver_pending_to_webhook

        state = state_for_home(home)
        try:
            result = deliver_pending_to_webhook(state_path=state.state_path, webhook_url=webhook)
        except WebhookDeliveryError as exc:
            raise typer.BadParameter(str(exc)) from exc
        echo_json(result.to_payload())


def _latest_pending_parked_id(*, home: Path | None) -> str:
    from zeus_agent.trust_loop_runtime import SQLiteApprovalQueue, SQLiteControlPlaneStore

    state = state_for_home(home)
    queue = SQLiteApprovalQueue(SQLiteControlPlaneStore(state.state_path))
    pending = queue.pending(now=datetime.now(timezone.utc))
    if not pending:
        raise typer.BadParameter("no pending parked ASK")
    return pending[-1].parked_action_id


def _resolve_parked(
    parked_action_id: str,
    *,
    deny: bool,
    confirm: bool,
    narrow_path: str | None,
    home: Path | None,
) -> None:
    from zeus_agent.graded_approval_runtime import GrantScope, issue_grant
    from zeus_agent.trust_loop_runtime import (
        ActionRisk,
        ReplayAuthorization,
        Reversibility,
        SQLiteApprovalQueue,
        SQLiteControlPlaneStore,
        SQLiteReplayAuthorizationStore,
    )

    state = state_for_home(home)
    store = SQLiteControlPlaneStore(state.state_path)
    queue = SQLiteApprovalQueue(store)
    try:
        parked = queue.get(parked_action_id)
    except KeyError:
        raise typer.BadParameter("unknown parked_action_id: {0}".format(parked_action_id))
    resolved = queue.resolve(parked_action_id, approved=not deny)
    if resolved.status != "approved":
        echo_json({"parked_action_id": parked_action_id, "status": resolved.status})
        return
    action = parked.action
    hard_risk = action.risk is ActionRisk.high or action.reversibility is Reversibility.irreversible
    replay_only = _approval_effect(parked) == "exact_payload_replay_once"
    if replay_only and narrow_path is None:
        now = datetime.now(timezone.utc)
        token_id = "replay.{0}.{1}".format(
            action.capability_id.replace(".", "_"),
            store.next_counter("replay_token_seq"),
        )
        SQLiteReplayAuthorizationStore(store).add(
            ReplayAuthorization(
                token_id=token_id,
                host=parked.host,
                session_id=parked.session_id,
                capability_id=action.capability_id,
                payload_hash=parked.payload_hash,
                created_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        echo_json(
            {
                "parked_action_id": parked_action_id,
                "status": "approved",
                "capability_id": action.capability_id,
                "replay": "approved_for_exact_payload_once",
                "replay_token_id": token_id,
                "confirmed": confirm,
                "next": (
                    "re-issue the same host action; do not paste Zeus operator commands "
                    "into the governed host"
                ),
            }
        )
        return
    if hard_risk and narrow_path is not None:
        raise typer.BadParameter("--narrow-path cannot authorize replay-only hard-risk actions")
    path = _narrowed_path(action_path=action.payload.get("path"), narrow_path=narrow_path)
    grant_scope = GrantScope.narrower if narrow_path is not None else GrantScope.once
    grant = issue_grant(
        grant_id="grant.parked.{0}.{1}".format(action.capability_id.replace(".", "_"), int(time.time())),
        capability_id=action.capability_id,
        scope=grant_scope,
        narrowed_paths=(path,) if path is not None else (),
        expires_at_epoch=int(time.time()) + 3600,
    )
    state.add_grant(grant)
    echo_json(
        {
            "parked_action_id": parked_action_id,
            "status": "approved",
            "capability_id": action.capability_id,
            "grant_id": grant.grant_id,
            "grant_scope": grant.scope.value,
            "confirmed": confirm,
            "narrowed_paths": list(grant.narrowed_paths),
            "next": "the host's re-issued call now passes ({0})".format(
                "covered_by_grant_{0}".format(grant.scope.value)
            ),
        }
    )


def _narrowed_path(*, action_path: object, narrow_path: str | None) -> str | None:
    if narrow_path is None:
        return action_path if isinstance(action_path, str) else None
    if not isinstance(action_path, str):
        raise typer.BadParameter("--narrow-path requires the parked action to include a path")
    normalized = narrow_path.rstrip("/") or "/"
    if action_path != normalized and not action_path.startswith(normalized.rstrip("/") + "/"):
        raise typer.BadParameter("--narrow-path must cover the parked action path")
    return normalized


def _approval_effect(parked: ParkedAction) -> str:
    from zeus_agent.operator_inbox_runtime import approval_effect_for

    return approval_effect_for(parked)
