from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import typer

from .approval_resolution import approval_effect, latest_pending_parked_id, resolve_parked
from .context import echo_json, state_for_home


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
        remember: bool = typer.Option(False, "--remember", help="With --parked: remember this approval as a scoped grant."),
        deny: bool = typer.Option(False, "--deny", help="With --parked: reject instead of approve."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.graded_approval_runtime import GrantScope, issue_grant

        if parked is not None and last:
            raise typer.BadParameter("use either --parked or --last, not both")
        if narrow_path is not None and parked is None and not last:
            raise typer.BadParameter("--narrow-path requires --parked or --last")
        if remember and parked is None and not last:
            raise typer.BadParameter("--remember requires --parked or --last")
        if remember and deny:
            raise typer.BadParameter("--remember cannot be combined with --deny")
        if last and not deny and not confirm:
            raise typer.BadParameter("--last approval requires --confirm")
        if parked is not None or last:
            target = parked if parked is not None else latest_pending_parked_id(home=home)
            resolve_parked(
                target,
                deny=deny,
                confirm=confirm,
                narrow_path=narrow_path,
                remember=remember,
                remember_hours=hours,
                home=home,
            )
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
                card["approval_effect"] = approval_effect(parked_item)
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
