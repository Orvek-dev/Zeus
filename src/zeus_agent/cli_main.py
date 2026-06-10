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
    """Control-plane status: coverage, decision mix, asks, chain integrity."""
    from zeus_agent.trust_loop_runtime import FlightRecorder, SQLiteEvidenceLedger

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
    _echo_json(
        {
            "home": str(state.root),
            "coverage": coverage.model_dump(mode="json"),
            "decision_mix": decision_mix,
            "asks": decision_mix.get("ask", 0),
            "chain_ok": recorder.ledger.verify_chain().ok,
            "standing_grants": len(state.load_grants().all()),
        }
    )


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
