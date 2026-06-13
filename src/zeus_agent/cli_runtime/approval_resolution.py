from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from .context import echo_json, state_for_home

if TYPE_CHECKING:
    from zeus_agent.trust_loop_runtime import ParkedAction


def latest_pending_parked_id(*, home: Path | None) -> str:
    from zeus_agent.trust_loop_runtime import SQLiteApprovalQueue, SQLiteControlPlaneStore

    state = state_for_home(home)
    queue = SQLiteApprovalQueue(SQLiteControlPlaneStore(state.state_path))
    pending = queue.pending(now=datetime.now(timezone.utc))
    if not pending:
        raise typer.BadParameter("no pending parked ASK")
    return pending[-1].parked_action_id


def resolve_parked(
    parked_action_id: str,
    *,
    deny: bool,
    confirm: bool,
    narrow_path: str | None,
    remember: bool,
    remember_hours: int,
    home: Path | None,
) -> None:
    from zeus_agent.trust_loop_runtime import (
        ActionRisk,
        Reversibility,
        SQLiteApprovalQueue,
        SQLiteControlPlaneStore,
    )

    state = state_for_home(home)
    store = SQLiteControlPlaneStore(state.state_path)
    queue = SQLiteApprovalQueue(store)
    try:
        parked = queue.get(parked_action_id)
    except KeyError:
        raise typer.BadParameter("unknown parked_action_id: {0}".format(parked_action_id))
    action = parked.action
    hard_risk = action.risk is ActionRisk.high or action.reversibility is Reversibility.irreversible
    if remember and hard_risk:
        raise typer.BadParameter("--remember cannot authorize hard-risk actions")
    if hard_risk and narrow_path is not None:
        raise typer.BadParameter("--narrow-path cannot authorize replay-only hard-risk actions")
    if narrow_path is not None:
        _narrowed_path(action_path=action.payload.get("path"), narrow_path=narrow_path)
    resolved = queue.resolve(parked_action_id, approved=not deny)
    if resolved.status != "approved":
        echo_json({"parked_action_id": parked_action_id, "status": resolved.status})
        return
    if remember:
        _issue_remembered_grant(state, parked, narrow_path=narrow_path, confirm=confirm, hours=remember_hours)
        return
    replay_only = approval_effect(parked) == "exact_payload_replay_once"
    if replay_only and narrow_path is None:
        _issue_replay_token(store, parked, confirm=confirm)
        return
    _issue_scoped_grant(state, parked, narrow_path=narrow_path, confirm=confirm)


def approval_effect(parked: ParkedAction) -> str:
    from zeus_agent.operator_inbox_runtime import approval_effect_for

    return approval_effect_for(parked)


def _issue_remembered_grant(
    state,
    parked: ParkedAction,
    *,
    narrow_path: str | None,
    confirm: bool,
    hours: int,
) -> None:
    from zeus_agent.graded_approval_runtime import GrantScope, issue_grant

    action = parked.action
    path = _narrowed_path(action_path=action.payload.get("path"), narrow_path=narrow_path)
    grant_scope = GrantScope.narrower if path is not None else GrantScope.session
    grant = issue_grant(
        grant_id="grant.parked.{0}.{1}".format(action.capability_id.replace(".", "_"), int(time.time())),
        capability_id=action.capability_id,
        scope=grant_scope,
        session_id=parked.session_id if grant_scope is GrantScope.session else None,
        narrowed_paths=(path,) if path is not None else (),
        expires_at_epoch=0 if hours <= 0 else int(time.time()) + hours * 3600,
    )
    state.add_grant(grant)
    echo_json(
        {
            "parked_action_id": parked.parked_action_id,
            "status": "approved",
            "capability_id": action.capability_id,
            "grant_id": grant.grant_id,
            "grant_scope": grant.scope.value,
            "remembered": True,
            "confirmed": confirm,
            "expires_at_epoch": grant.expires_at_epoch,
            "narrowed_paths": list(grant.narrowed_paths),
            "session_id": grant.session_id,
            "next": "the host's re-issued call now passes ({0})".format(
                "covered_by_grant_{0}".format(grant.scope.value)
            ),
        }
    )


def _issue_replay_token(store, parked: ParkedAction, *, confirm: bool) -> None:
    from zeus_agent.trust_loop_runtime import ReplayAuthorization, SQLiteReplayAuthorizationStore

    action = parked.action
    now = datetime.now(timezone.utc)
    token_id = "replay.{0}.{1}".format(action.capability_id.replace(".", "_"), store.next_counter("replay_token_seq"))
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
            "parked_action_id": parked.parked_action_id,
            "status": "approved",
            "capability_id": action.capability_id,
            "replay": "approved_for_exact_payload_once",
            "replay_token_id": token_id,
            "confirmed": confirm,
            "next": "re-issue the same host action; do not paste Zeus operator commands into the governed host",
        }
    )


def _issue_scoped_grant(state, parked: ParkedAction, *, narrow_path: str | None, confirm: bool) -> None:
    from zeus_agent.graded_approval_runtime import GrantScope, issue_grant

    action = parked.action
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
            "parked_action_id": parked.parked_action_id,
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
