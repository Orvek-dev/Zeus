"""Zeus product CLI — the ~10 user verbs of the control plane.

The legacy platform surface (300+ wave commands, the demoted executor) lives
under ``zeus dev`` and is imported lazily so the hook hot path stays fast.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

import typer

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
    host: str = typer.Argument("claude-code", help="Host gate: claude-code."),
    event: str = typer.Option("pre", "--event", help="pre (PreToolUse) or post (PostToolUse)."),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Hook entrypoint: JSON on stdin, decision JSON on stdout (Gate 0)."""
    if host != "claude-code":
        raise typer.BadParameter("unsupported host: {0}".format(host))
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    try:
        from zeus_agent.adapters.claude_code_hook import run_hook_event

        output = run_hook_event(_state(home), event, payload if isinstance(payload, dict) else {})
    except Exception as exc:  # fail closed, never brick the host session
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "[Zeus] internal error, falling back to ask: {0}".format(exc),
            }
        }
    typer.echo(json.dumps(output, ensure_ascii=False))


@app.command("connect")
def connect(
    host: str = typer.Argument("claude-code"),
    write: bool = typer.Option(False, "--write", help="Merge hook config into <project>/.claude/settings.json."),
    project_dir: Path = typer.Option(Path("."), "--project-dir"),
) -> None:
    """Self-onboarding: print (or write) the host's hook configuration."""
    if host == "hermes":
        from zeus_agent.adapters.hermes import hermes_connect_bundle

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
    capability_id: str = typer.Argument(..., help="Capability to license, e.g. fs.write"),
    scope: str = typer.Option("session", "--scope", help="once | session | narrower"),
    session_id: Optional[str] = typer.Option(None, "--session-id"),
    path: Optional[str] = typer.Option(None, "--path", help="Narrowed path prefix (scope=narrower)."),
    hours: int = typer.Option(8, "--hours", help="Grant lifetime in hours (0 = no expiry)."),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Issue a graded standing grant (once / session / narrower)."""
    from zeus_agent.graded_approval_runtime import GrantScope, issue_grant

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


@app.command("approvals")
def approvals(home: Optional[Path] = typer.Option(None, "--home")) -> None:
    """List standing grants (the licenses that silence repeat asks)."""
    store = _state(home).load_grants()
    _echo_json([grant.model_dump(mode="json") for grant in store.all()])


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
    _echo_json(
        {
            "home": str(state.root),
            "coverage": coverage.model_dump(mode="json"),
            "decision_mix": decision_mix,
            "asks": decision_mix.get("ask", 0),
            "chain_ok": recorder.ledger.verify_chain().ok,
            "standing_grants": len(state.load_grants().all()),
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
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    """Serve the governed LLM proxy (Gate 1): point the host's base_url here."""
    from zeus_agent.proxy_runtime import (
        LlmProxyEngine,
        run_proxy_server,
        seed_proxy_capability_store,
    )
    from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

    from zeus_agent.pairing_runtime import PairingManager
    from zeus_agent.zeusd_runtime import ZeusApiSurface

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
        rows.append(
            {
                "capability_id": capability_id,
                "status": record.status.value,
                "schema_hash": (record.schema_hash or "")[:12],
                "server": record.server_ref,
            }
        )
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
