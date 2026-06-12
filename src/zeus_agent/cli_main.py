"""Zeus product CLI — the ~10 user verbs of the control plane.

The legacy platform surface (300+ wave commands, the demoted executor) lives
under ``zeus dev`` and is imported lazily so the hook hot path stays fast.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer

if TYPE_CHECKING:
    from zeus_agent.graded_approval_runtime import ApprovalGrant
    from zeus_agent.trust_loop_runtime import ParkedAction

app = typer.Typer(
    no_args_is_help=True,
    help=(
        "Zeus — a local-first governance control plane for AI agents. "
        "Agent platforms plug in through gates; Zeus decides, records, and "
        "earns autonomy down to fewer asks."
    ),
)


def _default_home() -> Path:
    return Path.home() / ".zeus"


def _state(home: Optional[Path]):
    from zeus_agent.adapters.claude_code_hook import ControlPlaneState

    return ControlPlaneState(home if home is not None else _default_home())


def _echo_json(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _is_loopback(bind: str) -> bool:
    return bind.strip().lower() in {"127.0.0.1", "::1", "localhost", "[::1]"}


def _hermes_preflight(*, port: int, home: Optional[Path]) -> dict:
    """What Zeus can verify before a dogfood/soak run; host-side items that
    Zeus cannot reach (hermes config, hook allowlist, doctor) are returned as
    a manual checklist so nothing is silently assumed green."""
    import urllib.error
    import urllib.request

    from zeus_agent import __version__

    state = _state(home)
    home_ready = (state.root).is_dir()
    proxy_ok = False
    proxy_detail = "unreachable on 127.0.0.1:{0}".format(port)
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:{0}/health".format(port), timeout=2
        ) as response:
            body = json.loads(response.read().decode("utf-8"))
            proxy_ok = body.get("gate") == "llm_proxy"
            proxy_detail = body
    except (urllib.error.URLError, OSError, ValueError) as exc:
        proxy_detail = "unreachable: {0}".format(exc)

    return {
        "zeus_version": __version__,
        "checks": {
            "control_plane_home": {"ok": home_ready, "path": str(state.root)},
            "proxy_health": {"ok": proxy_ok, "detail": proxy_detail},
        },
        "manual": [
            "hermes config: provider `zeus` set + model.provider=zeus (not a bare base_url)",
            "hermes hooks allowlisted: `hermes hooks doctor` is green",
            "pairing approved: `zeus pair --approve <code>` was run for hermes",
            "PATH includes ~/.local/bin (hermes on PATH)",
            "proxy started with `--hook-owned-host hermes` (no double ask)",
        ],
        "soak_note": "for a 7-day soak, start from a FRESH control-plane home "
        "(zeus init --home <new>) — a dogfood ledger with synthetic/early-bridge "
        "records is not clean soak evidence. Record hermes + zeus versions first.",
        "ready": home_ready and proxy_ok,
    }


def _version_callback(value: bool) -> None:
    if value:
        from zeus_agent import __version__

        typer.echo("zeus-agent {0}".format(__version__))
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed zeus-agent version and exit.",
    ),
) -> None:
    return None


@app.command("init")
def init(home: Optional[Path] = typer.Option(None, "--home")) -> None:
    """Create the local control-plane home (ledger, trust, grants, taint)."""
    state = _state(home)
    state.build_engine()  # touches every store so first decide() is warm
    _echo_json(
        {
            "home": str(state.root),
            "ledger": str(state.ledger_path),
            "next": "zeus connect claude-code",
        }
    )


@app.command("hook")
def hook(
    host: str = typer.Argument("claude-code", help="Host gate: claude-code | hermes."),
    event: str = typer.Option("pre", "--event", help="pre (PreToolUse) or post (PostToolUse)."),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Hook entrypoint: JSON on stdin, decision JSON on stdout (Gate 0/3)."""
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    payload = payload if isinstance(payload, dict) else {}
    if host == "claude-code":
        try:
            from zeus_agent.adapters.claude_code_hook import run_hook_event

            output = run_hook_event(_state(home), event, payload)
        except Exception as exc:  # fail closed, never brick the host session
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": "[Zeus] internal error, falling back to ask: {0}".format(exc),
                }
            }
    elif host == "hermes":
        try:
            from zeus_agent.adapters.hermes import HermesGate

            gate = HermesGate(_state(home).build_engine())
            output = gate.post_tool_call(payload) if event == "post" else gate.pre_tool_call(payload)
        except Exception as exc:  # hermes pre-hook is blocking → fail closed to block
            output = {"action": "block", "reason": "[Zeus] internal error, failing closed: {0}".format(exc)}
    else:
        raise typer.BadParameter("unsupported host: {0} (use claude-code or hermes)".format(host))
    typer.echo(json.dumps(output, ensure_ascii=False))


@app.command("connect")
def connect(
    host: str = typer.Argument("claude-code"),
    write: bool = typer.Option(False, "--write", help="Merge hook config into <project>/.claude/settings.json."),
    project_dir: Path = typer.Option(Path("."), "--project-dir"),
    check: bool = typer.Option(False, "--check", help="Preflight the connection instead of printing config."),
    port: int = typer.Option(8788, "--port", help="Proxy port to probe with --check."),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Self-onboarding: print (or write) the host's hook configuration."""
    if host == "hermes":
        from zeus_agent.adapters.hermes import hermes_connect_bundle

        if check:
            _echo_json(_hermes_preflight(port=port, home=home))
            return
        _echo_json(hermes_connect_bundle())
        return
    if host == "openclaw":
        from zeus_agent.adapters.openclaw import openclaw_connect_bundle

        _echo_json(openclaw_connect_bundle())
        return
    if host != "claude-code":
        raise typer.BadParameter("unsupported host: {0}".format(host))
    hooks_config = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": "zeus hook claude-code"}],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": "zeus hook claude-code --event post"}],
                }
            ],
        }
    }
    if not write:
        _echo_json(hooks_config)
        typer.echo("# add the block above to .claude/settings.json, or rerun with --write", err=True)
        return
    settings_path = project_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise typer.BadParameter("existing settings.json is not valid JSON; not overwriting")
    merged_hooks = dict(existing.get("hooks", {}))
    for event_name, entries in hooks_config["hooks"].items():
        current = list(merged_hooks.get(event_name, []))
        if not any("zeus hook claude-code" in json.dumps(entry) for entry in current):
            current.extend(entries)
        merged_hooks[event_name] = current
    existing["hooks"] = merged_hooks
    settings_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    _echo_json({"written": str(settings_path), "gate": "claude-code PreToolUse/PostToolUse"})


@app.command("decide")
def decide(
    request_json: Optional[str] = typer.Option(None, "--request-json", help="DecisionRequest JSON; defaults to stdin."),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """One-shot Decision API call for hosts and scripts."""
    from pydantic import ValidationError

    from zeus_agent.decision_api_runtime import DecisionRequest

    raw = request_json if request_json is not None else sys.stdin.read()
    try:
        request = DecisionRequest.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        _echo_json({"decision": "deny", "reason": "malformed_decision_request", "error": str(exc)})
        raise typer.Exit(code=1)
    engine = _state(home).build_engine()
    response = engine.decide(request)
    _echo_json(response.model_dump(mode="json"))


@app.command("record")
def record(
    receipt: str = typer.Option(..., "--receipt", help="Decision receipt id (trust.ev.NNNNNN)."),
    status: str = typer.Option(..., "--status", help="success | failure | error"),
    cost: int = typer.Option(0, "--cost", help="Actual cost units spent."),
    note: Optional[str] = typer.Option(None, "--note"),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Bind a host execution outcome to its decision receipt."""
    from zeus_agent.trust_loop_runtime import ExecutionOutcome, ExecutionStatus

    try:
        parsed_status = ExecutionStatus(status)
    except ValueError:
        raise typer.BadParameter("status must be success, failure, or error")
    state = _state(home)
    engine = state.build_engine()
    outcome_record_id = engine.record(
        receipt,
        ExecutionOutcome(status=parsed_status, cost_actual_units=max(cost, 0), notes=note),
    )
    _echo_json({"outcome_record_id": outcome_record_id, "caused_by": receipt})


@app.command("approve")
def approve(
    capability_id: Optional[str] = typer.Argument(None, help="Capability to license, e.g. fs.write"),
    scope: str = typer.Option("session", "--scope", help="once | session | narrower"),
    session_id: Optional[str] = typer.Option(None, "--session-id"),
    path: Optional[str] = typer.Option(None, "--path", help="Narrowed path prefix (scope=narrower)."),
    hours: int = typer.Option(8, "--hours", help="Grant lifetime in hours (0 = no expiry)."),
    parked: Optional[str] = typer.Option(None, "--parked", help="Resolve a parked ASK by its parked_action_id."),
    deny: bool = typer.Option(False, "--deny", help="With --parked: reject instead of approve."),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Issue a graded standing grant, or resolve a parked ASK with --parked."""
    from zeus_agent.graded_approval_runtime import GrantScope, issue_grant

    if parked is not None:
        _resolve_parked(parked, deny=deny, home=home)
        return
    if capability_id is None:
        raise typer.BadParameter("provide a capability_id, or use --parked <id>")
    try:
        parsed_scope = GrantScope(scope)
    except ValueError:
        raise typer.BadParameter("scope must be once, session, or narrower")
    if parsed_scope is GrantScope.session and session_id is None:
        raise typer.BadParameter("--session-id is required for scope=session")
    if parsed_scope is GrantScope.narrower and path is None:
        raise typer.BadParameter("--path is required for scope=narrower")
    grant = issue_grant(
        grant_id="grant.{0}.{1}".format(capability_id.replace(".", "_"), int(time.time())),
        capability_id=capability_id,
        scope=parsed_scope,
        session_id=session_id,
        narrowed_paths=(path,) if path is not None else (),
        expires_at_epoch=0 if hours <= 0 else int(time.time()) + hours * 3600,
    )
    _state(home).add_grant(grant)
    _echo_json(grant.model_dump(mode="json"))


def _resolve_parked(parked_action_id: str, *, deny: bool, home: Optional[Path]) -> None:
    """Operator cockpit for a parked ASK: resolve the queue row, and on approve
    issue a matching once-grant so the host's re-issued call passes. Hard-risk
    actions are never licensed — the human must approve each instance."""
    from zeus_agent.graded_approval_runtime import GrantScope, issue_grant
    from datetime import datetime, timedelta, timezone

    from zeus_agent.trust_loop_runtime import (
        ActionRisk,
        ReplayAuthorization,
        Reversibility,
        SQLiteApprovalQueue,
        SQLiteControlPlaneStore,
        SQLiteReplayAuthorizationStore,
    )

    state = _state(home)
    store = SQLiteControlPlaneStore(state.state_path)
    queue = SQLiteApprovalQueue(store)
    try:
        parked = queue.get(parked_action_id)
    except KeyError:
        raise typer.BadParameter("unknown parked_action_id: {0}".format(parked_action_id))
    resolved = queue.resolve(parked_action_id, approved=not deny)
    if resolved.status != "approved":
        _echo_json({"parked_action_id": parked_action_id, "status": resolved.status})
        return
    action = parked.action
    hard_risk = action.risk is ActionRisk.high or action.reversibility is Reversibility.irreversible
    if hard_risk:
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
        _echo_json(
            {
                "parked_action_id": parked_action_id,
                "status": "approved",
                "capability_id": action.capability_id,
                "replay": "approved_for_exact_payload_once",
                "replay_token_id": token_id,
                "next": (
                    "re-issue the same host action; do not paste Zeus operator commands "
                    "into the governed host"
                ),
            }
        )
        return
    path = action.payload.get("path") if isinstance(action.payload.get("path"), str) else None
    grant = issue_grant(
        grant_id="grant.parked.{0}.{1}".format(action.capability_id.replace(".", "_"), int(time.time())),
        capability_id=action.capability_id,
        scope=GrantScope.once,
        narrowed_paths=(path,) if path is not None else (),
        expires_at_epoch=int(time.time()) + 3600,
    )
    state.add_grant(grant)
    _echo_json(
        {
            "parked_action_id": parked_action_id,
            "status": "approved",
            "capability_id": action.capability_id,
            "grant_id": grant.grant_id,
            "next": "the host's re-issued call now passes once (covered_by_grant_once)",
        }
    )


@app.command("approvals")
def approvals(
    pending: bool = typer.Option(False, "--pending", help="Show parked ASKs awaiting resolution."),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """List standing grants, or parked ASKs with --pending (the operator inbox)."""
    state = _state(home)
    if pending:
        from datetime import datetime, timezone

        from zeus_agent.trust_loop_runtime import SQLiteApprovalQueue, SQLiteControlPlaneStore

        queue = SQLiteApprovalQueue(SQLiteControlPlaneStore(state.state_path))
        rows = queue.pending(now=datetime.now(timezone.utc))
        _echo_json(
            [
                {
                    "parked_action_id": parked.parked_action_id,
                    "capability_id": parked.action.capability_id,
                    "run_id": parked.action.run_id,
                    "risk": parked.action.risk.value,
                    "reversibility": parked.action.reversibility.value,
                    "host": parked.host,
                    "session_id": parked.session_id,
                    "payload": parked.action.payload,
                    "approval_effect": _approval_effect(parked),
                    "operator_note": (
                        "resolve in Zeus control tower or a separate operator terminal; "
                        "do not paste this command into the governed host"
                    ),
                    "created_at": parked.created_at.isoformat(),
                    "expires_at": parked.expires_at.isoformat(),
                    "resolve": "zeus approve --parked {0}".format(parked.parked_action_id),
                }
                for parked in rows
            ]
        )
        return
    _echo_json([grant.model_dump(mode="json") for grant in state.load_grants().all()])


def _approval_effect(parked: "ParkedAction") -> str:
    from zeus_agent.trust_loop_runtime import ActionRisk, Reversibility

    action = parked.action
    hard_risk = action.risk is ActionRisk.high or action.reversibility is Reversibility.irreversible
    return "exact_payload_replay_once" if hard_risk else "once_grant"


@app.command("ledger")
def ledger(
    tail: int = typer.Option(20, "--tail", help="Show the last N records."),
    why: Optional[str] = typer.Option(None, "--why", help="Walk the causal chain of a record id."),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Inspect the evidence ledger (console principal: full view)."""
    from zeus_agent.trust_loop_runtime import FlightRecorder, SQLiteEvidenceLedger

    state = _state(home)
    recorder = FlightRecorder(SQLiteEvidenceLedger(state.ledger_path))
    if why is not None:
        _echo_json(list(recorder.why(why)))
        return
    records = recorder.ledger.records()
    _echo_json(records[-max(tail, 0):])


@app.command("why", help="Show why a parked action or record happened.")
def why(
    parked: Optional[str] = typer.Option(None, "--parked", help="Parked action id."),
    record: Optional[str] = typer.Option(None, "--record", help="Ledger record id."),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    from zeus_agent.trust_loop_runtime import (
        FlightRecorder,
        SQLiteApprovalQueue,
        SQLiteControlPlaneStore,
        SQLiteEvidenceLedger,
    )

    state = _state(home)
    recorder = FlightRecorder(SQLiteEvidenceLedger(state.ledger_path))
    if record is not None:
        _echo_json({"record_id": record, "chain": list(recorder.why(record))})
        return
    if parked is None:
        raise typer.BadParameter("provide --parked <id> or --record <id>")
    queue = SQLiteApprovalQueue(SQLiteControlPlaneStore(state.state_path))
    try:
        item = queue.get(parked)
    except KeyError:
        raise typer.BadParameter("unknown parked_action_id: {0}".format(parked))
    _echo_json(
        {
            "parked_action_id": item.parked_action_id,
            "status": item.status,
            "capability_id": item.action.capability_id,
            "host": item.host,
            "session_id": item.session_id,
            "approval_effect": _approval_effect(item),
            "operator_note": (
                "resolve in Zeus control tower or a separate operator terminal; "
                "do not paste Zeus commands into the governed host"
            ),
            "timeline": _timeline_for_parked(item, recorder.ledger.records()),
        }
    )


def _timeline_for_parked(
    parked: "ParkedAction", records: list[dict[str, object]]
) -> list[dict[str, object]]:
    timeline: list[dict[str, object]] = []
    decision_receipt_ids = _decision_receipt_ids_for_parked(parked, records)
    for record in records:
        payload = _record_payload(record)
        if not _matches_parked(parked, record, payload, decision_receipt_ids):
            continue
        row: dict[str, object] = {
            "seq": record["seq"],
            "record_id": record["record_id"],
            "kind": record["kind"],
            "run_id": record["run_id"],
            "capability_id": payload.get("capability_id"),
        }
        for field in ("host", "surface", "decision", "reason", "governed"):
            if field in payload:
                row[field] = payload[field]
        if "decision_receipt_record_id" in payload:
            row["decision_receipt_record_id"] = payload["decision_receipt_record_id"]
        timeline.append(row)
    return timeline


def _decision_receipt_ids_for_parked(
    parked: "ParkedAction", records: list[dict[str, object]]
) -> set[str]:
    receipt_ids: set[str] = set()
    for record in records:
        if str(record["kind"]) != "decision_receipt":
            continue
        payload = _record_payload(record)
        if _decision_receipt_matches_parked(parked, record, payload):
            receipt_ids.add(str(record["record_id"]))
    return receipt_ids


def _decision_receipt_matches_parked(
    parked: "ParkedAction", record: dict[str, object], payload: dict[str, object]
) -> bool:
    if str(record["run_id"]) != parked.action.run_id:
        return False
    if payload.get("capability_id") != parked.action.capability_id:
        return False
    if parked.session_id and payload.get("session_id") not in {None, parked.session_id}:
        return False
    action_id = payload.get("action_id")
    if action_id is not None:
        return action_id == parked.action.action_id
    action_payload_hash = payload.get("action_payload_hash")
    if action_payload_hash is not None:
        return action_payload_hash == parked.payload_hash
    return payload.get("args") == parked.action.payload


def _matches_parked(
    parked: "ParkedAction",
    record: dict[str, object],
    payload: dict[str, object],
    decision_receipt_ids: set[str],
) -> bool:
    kind = str(record["kind"])
    if kind == "decision_receipt":
        return str(record["record_id"]) in decision_receipt_ids
    if kind == "gate_observation":
        receipt_id = payload.get("decision_receipt_record_id")
        return isinstance(receipt_id, str) and receipt_id in decision_receipt_ids
    return False


def _record_payload(record: dict[str, object]) -> dict[str, object]:
    try:
        payload = json.loads(str(record["payload_json"]))
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _grant_status_counts(grants: tuple["ApprovalGrant", ...], *, now_epoch: int) -> dict[str, int]:
    counts = {"active": 0, "consumed": 0, "expired": 0, "total": len(grants)}
    for grant in grants:
        if grant.consumed:
            counts["consumed"] += 1
        elif grant.expires_at_epoch != 0 and now_epoch >= grant.expires_at_epoch:
            counts["expired"] += 1
        else:
            counts["active"] += 1
    return counts


@app.command("status")
def status(home: Optional[Path] = typer.Option(None, "--home")) -> None:
    """Control-plane status: coverage, decision mix, asks, chain, wallet."""
    from datetime import datetime, timezone

    from zeus_agent.proxy_runtime import KV_LAST_REQUEST_AT, KV_LAST_RESPONSE_AT, KV_SECRET_FINDINGS
    from zeus_agent.trust_loop_runtime import (
        FlightRecorder,
        SQLiteControlPlaneStore,
        SQLiteEvidenceLedger,
    )
    from zeus_agent.wallet_runtime import weekly_spend_digest

    state = _state(home)
    recorder = FlightRecorder(SQLiteEvidenceLedger(state.ledger_path))
    decision_mix: dict[str, int] = {}
    for item in recorder.ledger.records():
        if str(item["kind"]) != "decision_receipt":
            continue
        try:
            payload = json.loads(str(item["payload_json"]))
        except ValueError:
            continue
        decision = str(payload.get("decision", "unknown"))
        decision_mix[decision] = decision_mix.get(decision, 0) + 1
    coverage = recorder.coverage()
    now = datetime.now(timezone.utc)
    store = SQLiteControlPlaneStore(state.state_path)
    watchdog: dict[str, object] = {
        "last_request_at": store.kv_get(KV_LAST_REQUEST_AT),
        "last_response_at": store.kv_get(KV_LAST_RESPONSE_AT),
        "secret_findings": int(store.kv_get(KV_SECRET_FINDINGS) or 0),
    }
    request_at = _parse_ts(watchdog["last_request_at"])
    response_at = _parse_ts(watchdog["last_response_at"])
    if request_at is not None and (response_at is None or response_at < request_at):
        watchdog["waiting_on_provider_seconds"] = int((now - request_at).total_seconds())
    grants = _grant_status_counts(state.load_grants().all(), now_epoch=int(now.timestamp()))
    _echo_json(
        {
            "home": str(state.root),
            "coverage": coverage.model_dump(mode="json"),
            "decision_mix": decision_mix,
            "asks": decision_mix.get("ask", 0),
            "chain_ok": recorder.ledger.verify_chain().ok,
            "standing_grants": grants["active"],
            "grants": grants,
            "wallet_week": weekly_spend_digest(recorder, now=now),
            "budgets": [
                {"scope": row[0], "id": row[1], "limit_units": row[2], "spent_units": row[3]}
                for row in store.budget_rows()
            ],
            "proxy": watchdog,
        }
    )


def _parse_ts(value: object):
    from datetime import datetime

    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@app.command("proxy")
def proxy(
    upstream: str = typer.Option(..., "--upstream", help="Upstream base, e.g. https://api.openai.com"),
    port: int = typer.Option(8788, "--port"),
    bind: str = typer.Option("127.0.0.1", "--bind", help="Listen address (local-first by default)."),
    require_v1_auth: bool = typer.Option(
        False, "--require-v1-auth", help="Require an x-zeus-v1-token on /v1 requests."
    ),
    unsafe_no_v1_auth: bool = typer.Option(
        False, "--unsafe-no-v1-auth", help="Allow a non-loopback bind with NO /v1 auth (dangerous)."
    ),
    hook_owned_host: list[str] = typer.Option(
        [],
        "--hook-owned-host",
        help="Host whose own blocking pre_tool_call hook owns the ASK (proxy defers soft asks to it). Repeatable.",
    ),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Serve the governed LLM proxy (Gate 1): point the host's base_url here."""
    from zeus_agent.decision_api_runtime import HostKind
    from zeus_agent.proxy_runtime import (
        LlmProxyEngine,
        run_proxy_server,
        seed_proxy_capability_store,
    )
    from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

    from zeus_agent.pairing_runtime import PairingManager
    from zeus_agent.zeusd_runtime import ZeusApiSurface

    try:
        owned = frozenset(HostKind(h.strip().lower().replace("-", "_")) for h in hook_owned_host)
    except ValueError as exc:
        raise typer.BadParameter("unknown --hook-owned-host: {0}".format(exc)) from exc

    # /v1 is spoken by vanilla SDKs (static headers only) so it can't be
    # HMAC-paired like /zeus. On a non-loopback bind that means an unauthenticated
    # /v1 trusts whoever can reach the port — refuse unless the operator opts into
    # token auth or explicitly accepts the risk.
    if not _is_loopback(bind) and not require_v1_auth and not unsafe_no_v1_auth:
        raise typer.BadParameter(
            "non-loopback --bind {0} exposes /v1 with no auth; pass --require-v1-auth "
            "(issue tokens with `zeus pair --issue-v1-token <host>`) or --unsafe-no-v1-auth "
            "to accept the risk".format(bind)
        )

    state = _state(home)
    store = SQLiteControlPlaneStore(state.state_path)
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    proxy_engine = LlmProxyEngine(
        engine=engine,
        store=store,
        persist_taint=state.save_taint,
        hook_owned_hosts=owned,
    )
    pairing = PairingManager(store)
    api = ZeusApiSurface(engine=engine, pairing=pairing)
    typer.echo(
        json.dumps(
            {
                "listening": "http://{0}:{1}".format(bind, port),
                "surfaces": ["/v1 (llm proxy)", "/zeus (decide/record/brief, pairing-gated)"],
                "upstream": upstream,
                "v1_auth": "required" if require_v1_auth else "open (loopback)" if _is_loopback(bind) else "OPEN (unsafe)",
                "note": "model keys stay host-side; auth headers pass through",
            }
        ),
        err=True,
    )
    run_proxy_server(
        host=bind,
        port=port,
        engine=proxy_engine,
        upstream_base=upstream,
        api=api,
        v1_token_required=require_v1_auth,
        pairing=pairing,
    )


@app.command("budget")
def budget(
    scope: Optional[str] = typer.Option(None, "--scope", help="run | objective | fleet"),
    scope_id: Optional[str] = typer.Option(None, "--id", help="run/objective id (fleet uses 'fleet')."),
    limit: Optional[int] = typer.Option(None, "--limit", help="Max units (micro-USD) for the scope."),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Show budgets, or set a hard pre-call limit for a scope."""
    from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

    store = SQLiteControlPlaneStore(_state(home).state_path)
    if limit is not None:
        if scope not in {"run", "objective", "fleet"}:
            raise typer.BadParameter("--scope must be run, objective, or fleet")
        resolved_id = scope_id if scope_id is not None else ("fleet" if scope == "fleet" else None)
        if resolved_id is None:
            raise typer.BadParameter("--id is required for run/objective scopes")
        store.set_budget_limit(scope, resolved_id, max(limit, 0))
    _echo_json(
        [
            {"scope": row[0], "id": row[1], "limit_units": row[2], "spent_units": row[3]}
            for row in store.budget_rows()
        ]
    )


@app.command("policy")
def policy(
    apply: Optional[str] = typer.Option(None, "--apply", help="Apply a policy pack by name."),
    confirm: bool = typer.Option(False, "--confirm", help="Operator confirmation for --apply/--rule."),
    rule: Optional[str] = typer.Option(None, "--rule", help='NL rule, e.g. "weekly budget $12".'),
    hygiene_mode: Optional[str] = typer.Option(
        None, "--hygiene-mode", help="Proxy log-hygiene mode: count|redact|block|ask."
    ),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Policy packs and NL rules — every change is governed and ledgered."""
    from zeus_agent.nl_policy_runtime import apply_rule_diff, parse_nl_rule, supported_grammar
    from zeus_agent.policy_pack_runtime import BUILTIN_PACKS, apply_pack, pack_by_name
    from zeus_agent.proxy_runtime import KV_HYGIENE_MODE, HygieneMode, hygiene_mode_of
    from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

    state = _state(home)
    store = SQLiteControlPlaneStore(state.state_path)
    if apply is not None:
        pack = pack_by_name(apply)
        if pack is None:
            raise typer.BadParameter("unknown pack: {0}".format(apply))
        _echo_json(apply_pack(pack, engine=state.build_engine(), store=store, confirmed=confirm))
        return
    if rule is not None:
        diff = parse_nl_rule(rule)
        if diff is None:
            _echo_json({"parsed": False, "supported": list(supported_grammar())})
            raise typer.Exit(code=1)
        if not confirm:
            _echo_json({"parsed": True, "preview": diff.preview, "next": "rerun with --confirm"})
            return
        _echo_json(apply_rule_diff(diff, store))
        return
    if hygiene_mode is not None:
        try:
            mode = HygieneMode(hygiene_mode.strip().lower())
        except ValueError as exc:
            raise typer.BadParameter("hygiene mode must be one of: count, redact, block, ask") from exc
        engine = state.build_engine()
        # governance of governance: the change itself is a ledgered decision —
        # an unconfirmed preview parks as an ASK receipt, --confirm allows it.
        event = engine.recorder.record_decision(
            run_id="run.policy.hygiene",
            payload={
                "capability_id": "policy.change",
                "decision": "allow" if confirm else "ask",
                "reason": "hygiene_mode_set:{0}".format(mode.value),
                "principal_id": "operator.local",
            },
        )
        if not confirm:
            _echo_json(
                {
                    "parsed": True,
                    "preview": "set proxy hygiene mode → {0}".format(mode.value),
                    "next": "rerun with --confirm",
                    "receipt_id": event.record_id,
                }
            )
            return
        store.kv_set(KV_HYGIENE_MODE, mode.value)
        _echo_json({"applied": True, "hygiene_mode": mode.value, "receipt_id": event.record_id})
        return
    _echo_json(
        {
            "active_pack": store.kv_get("policy.active_pack"),
            "quiet_hours": store.kv_get("policy.quiet_hours"),
            "hygiene_mode": hygiene_mode_of(store).value,
            "packs": [
                {"name": pack.name, "description": pack.description} for pack in BUILTIN_PACKS
            ],
        }
    )


@app.command("digest")
def digest(
    ack: bool = typer.Option(False, "--ack", help="Acknowledge this week's digest (dead-man reset)."),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Weekly governance digest — where NOTIFY-tier actions land."""
    from datetime import datetime, timezone

    from zeus_agent.digest_runtime import ack_digest, build_digest
    from zeus_agent.trust_loop_runtime import (
        FlightRecorder,
        SQLiteControlPlaneStore,
        SQLiteEvidenceLedger,
        SQLiteTrustStatStore,
    )

    state = _state(home)
    store = SQLiteControlPlaneStore(state.state_path)
    now = datetime.now(timezone.utc)
    if ack:
        _echo_json(ack_digest(store, now=now))
        return
    recorder = FlightRecorder(SQLiteEvidenceLedger(state.ledger_path))
    _echo_json(build_digest(recorder, store, SQLiteTrustStatStore(state.trust_path), now=now))


@app.command("pair")
def pair(
    approve_code: Optional[str] = typer.Option(None, "--approve", help="Approve a host's pairing code."),
    revoke_code: Optional[str] = typer.Option(None, "--revoke", help="Revoke a pairing."),
    request_host: Optional[str] = typer.Option(None, "--request", help="(adapter side) request a pairing for a host name."),
    issue_v1_token: Optional[str] = typer.Option(
        None, "--issue-v1-token", help="Issue a static /v1 proxy token for a host name (shown once)."
    ),
    token_ttl_days: int = typer.Option(
        30, "--token-ttl-days", help="Expiry for --issue-v1-token (0 = never expires)."
    ),
    revoke_v1_token: Optional[str] = typer.Option(
        None, "--revoke-v1-token", help="Revoke a previously issued /v1 token."
    ),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Approve host pairings — the 1-tap trust step that is never skipped."""
    from zeus_agent.pairing_runtime import PairingManager
    from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

    manager = PairingManager(SQLiteControlPlaneStore(_state(home).state_path))
    if request_host is not None:
        _echo_json(manager.request(request_host))
        return
    if issue_v1_token is not None:
        _echo_json(manager.issue_v1_token(issue_v1_token, ttl_days=token_ttl_days))
        return
    if revoke_v1_token is not None:
        _echo_json({"revoked": manager.revoke_v1_token(revoke_v1_token)})
        return
    if approve_code is not None:
        _echo_json({"approved": manager.approve(approve_code), "code": approve_code})
        return
    if revoke_code is not None:
        _echo_json({"revoked": manager.revoke(revoke_code), "code": revoke_code})
        return
    raise typer.BadParameter(
        "use --approve CODE, --revoke CODE, --request HOST, --issue-v1-token HOST, "
        "or --revoke-v1-token TOKEN"
    )


@app.command("brief")
def brief(
    session_id: str = typer.Option(..., "--session-id", help="Host session to brief."),
    principal: str = typer.Option("agent.unknown", "--principal"),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Session-recovery briefing: scoped, masked, ledgered, tainted-untrusted."""
    from zeus_agent.trust_loop_runtime import (
        FlightRecorder,
        GovernedLedgerReader,
        LedgerPrincipalKind,
        SQLiteEvidenceLedger,
    )

    state = _state(home)
    reader = GovernedLedgerReader(FlightRecorder(SQLiteEvidenceLedger(state.ledger_path)))
    result = reader.read(
        principal_kind=LedgerPrincipalKind.agent,
        principal_id=principal,
        session_id=session_id,
    )
    _echo_json(result.model_dump(mode="json"))


def _gateway_parts(home: Optional[Path]):
    from zeus_agent.mcp_gateway_runtime import McpGateway, StdioMcpClient
    from zeus_agent.proxy_runtime import seed_proxy_capability_store
    from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

    state = _state(home)
    servers_path = state.root / "mcp-servers.json"
    clients: list = []
    if servers_path.exists():
        try:
            config = json.loads(servers_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            config = {}
        for name, spec in (config.get("servers") or {}).items():
            command = spec.get("command") if isinstance(spec, dict) else None
            if isinstance(command, list) and command:
                clients.append(StdioMcpClient(str(name), [str(part) for part in command]))
    gateway = McpGateway(
        engine=state.build_engine(capabilities=seed_proxy_capability_store()),
        store=SQLiteControlPlaneStore(state.state_path),
        downstreams=tuple(client.downstream() for client in clients),
        persist_taint=state.save_taint,
    )
    return state, gateway


@app.command("gateway")
def gateway_serve(
    home: Optional[Path] = typer.Option(None, "--home"),
    session_id: str = typer.Option("mcp-gateway.default", "--session-id"),
    principal: str = typer.Option("agent.mcp_client", "--principal"),
) -> None:
    """Serve the MCP gateway over stdio (Gate 2): hosts connect to Zeus only."""
    from zeus_agent.mcp_gateway_runtime import GatewaySession, serve_stdio

    _state_obj, gateway = _gateway_parts(home)
    gateway.sync_tools()
    serve_stdio(gateway, GatewaySession(principal_id=principal, session_id=session_id))


@app.command("mcp")
def mcp(
    sync: bool = typer.Option(False, "--sync", help="Import/reconcile downstream tools."),
    approve: Optional[str] = typer.Option(None, "--approve", help="De-quarantine a tool after review."),
    side_effect: Optional[str] = typer.Option(None, "--side-effect", help="Reviewed class: none|local_write|account_write|public_write."),
    reversibility: Optional[str] = typer.Option(None, "--reversibility", help="Reviewed class: reversible|compensable|irreversible."),
    tool_budget: Optional[str] = typer.Option(None, "--tool-budget", help="capability_id=N max calls."),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Inspect and review gateway-imported MCP tools (quarantine registry)."""
    from zeus_agent.capability_registry_runtime import CapabilityRecord, SideEffectClass
    from zeus_agent.trust_loop_runtime import Reversibility, SQLiteControlPlaneStore

    state, gateway = _gateway_parts(home)
    if sync:
        report = gateway.sync_tools()
        _echo_json(report.model_dump(mode="json"))
        return
    if approve is not None:
        try:
            parsed_side_effect = SideEffectClass(side_effect) if side_effect else None
            parsed_reversibility = Reversibility(reversibility) if reversibility else None
        except ValueError as exc:
            raise typer.BadParameter(str(exc))
        approved = gateway.approve_tool(
            approve, side_effect=parsed_side_effect, reversibility=parsed_reversibility
        )
        _echo_json({"approved": approved, "capability_id": approve})
        return
    if tool_budget is not None:
        capability_id, _, raw_limit = tool_budget.partition("=")
        if not capability_id or not raw_limit.isdigit():
            raise typer.BadParameter("--tool-budget expects capability_id=N")
        SQLiteControlPlaneStore(state.state_path).set_budget_limit(
            "capability", capability_id, int(raw_limit)
        )
        _echo_json({"capability_id": capability_id, "max_calls": int(raw_limit)})
        return
    store = SQLiteControlPlaneStore(state.state_path)
    rows = []
    for capability_id, raw in store.capability_all():
        try:
            record = CapabilityRecord.model_validate_json(raw)
        except ValueError:
            continue
        if record.server_ref is None and not capability_id.startswith("mcp."):
            continue  # only gateway-imported MCP tools belong in this registry
        rows.append(
            {
                "capability_id": capability_id,
                "status": record.status.value,
                "schema_hash": (record.schema_hash or "")[:12],
                "server": record.server_ref,
            }
        )
    if not rows:
        # D8: an empty registry reads as broken; it usually just means no
        # downstream MCP server has been imported yet.
        _echo_json(
            {
                "tools": [],
                "note": "no downstream MCP tools imported yet — this is expected until a "
                "downstream server is added. Run `zeus mcp --sync` after configuring a "
                "downstream MCP server; imported tools arrive quarantined for review.",
            }
        )
        return
    _echo_json(rows)


@app.command(
    "dev",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
        "help_option_names": [],
    },
    help="Legacy platform surface and the demoted executor (conformance harness).",
)
def dev(ctx: typer.Context) -> None:
    from typer.main import get_command

    from zeus_agent.cli import app as legacy_app

    command = get_command(legacy_app)
    command.main(args=list(ctx.args), prog_name="zeus dev", standalone_mode=True)
