from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import typer

from .context import default_home, echo_json, state_for_home


def register_core_commands(app: typer.Typer) -> None:
    @app.command("init", help="Create the local control-plane home (ledger, trust, grants, taint).")
    def init(home: Path | None = typer.Option(None, "--home")) -> None:
        state = state_for_home(home)
        state.build_engine()
        echo_json(
            {
                "home": str(state.root),
                "ledger": str(state.ledger_path),
                "next": "zeus connect claude-code",
            }
        )

    @app.command("hook", help="Hook entrypoint: JSON on stdin, decision JSON on stdout (Gate 0/3).")
    def hook(
        host: str = typer.Argument("claude-code", help="Host gate: claude-code | hermes."),
        event: str = typer.Option("pre", "--event", help="pre, post, stop, or complete."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        raw = sys.stdin.read()
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            payload = {}
        payload = payload if isinstance(payload, dict) else {}
        if host == "claude-code":
            try:
                from zeus_agent.adapters.claude_code_hook import run_hook_event

                output = run_hook_event(state_for_home(home), event, payload)
            except Exception as exc:
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": (
                            "[Zeus] internal error, falling back to ask: {0}".format(exc)
                        ),
                    }
                }
        elif host == "hermes":
            try:
                if event in {"stop", "complete"}:
                    from zeus_agent.completion_gate_runtime import evaluate_completion_claim

                    result = evaluate_completion_claim(payload)
                    typer.echo(json.dumps(result.to_hook_output(), ensure_ascii=False))
                    return
                from zeus_agent.adapters.hermes import HermesGate

                gate = HermesGate(state_for_home(home).build_engine())
                output = gate.post_tool_call(payload) if event == "post" else gate.pre_tool_call(payload)
            except Exception as exc:
                output = {
                    "action": "block",
                    "reason": "[Zeus] internal error, failing closed: {0}".format(exc),
                }
        else:
            raise typer.BadParameter("unsupported host: {0} (use claude-code or hermes)".format(host))
        typer.echo(json.dumps(output, ensure_ascii=False))

    @app.command("connect", help="Self-onboarding: print or write the host's hook configuration.")
    def connect(
        host: str = typer.Argument("claude-code"),
        write: bool = typer.Option(False, "--write", help="Merge hook config into <project>/.claude/settings.json."),
        project_dir: Path = typer.Option(Path("."), "--project-dir"),
        check: bool = typer.Option(False, "--check", help="Preflight the connection instead of printing config."),
        port: int = typer.Option(8788, "--port", help="Proxy port to probe with --check."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        if host == "hermes":
            from zeus_agent.adapters.hermes import hermes_connect_bundle

            if check:
                echo_json(_hermes_preflight(port=port, home=home))
                return
            hermes_home = home if home is not None else default_home()
            echo_json(
                hermes_connect_bundle(
                    zeus_bin=_resolved_zeus_bin(),
                    zeus_home=str(hermes_home.expanduser().resolve()),
                )
            )
            return
        if host == "openclaw":
            from zeus_agent.adapters.openclaw import openclaw_connect_bundle

            echo_json(openclaw_connect_bundle())
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
            echo_json(hooks_config)
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
        echo_json({"written": str(settings_path), "gate": "claude-code PreToolUse/PostToolUse"})

    @app.command("decide", help="One-shot Decision API call for hosts and scripts.")
    def decide(
        request_json: str | None = typer.Option(None, "--request-json", help="DecisionRequest JSON; defaults to stdin."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from pydantic import ValidationError

        from zeus_agent.decision_api_runtime import DecisionRequest

        raw = request_json if request_json is not None else sys.stdin.read()
        try:
            request = DecisionRequest.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as exc:
            echo_json({"decision": "deny", "reason": "malformed_decision_request", "error": str(exc)})
            raise typer.Exit(code=1)
        response = state_for_home(home).build_engine().decide(request)
        echo_json(response.model_dump(mode="json"))

    @app.command("record", help="Bind a host execution outcome to its decision receipt.")
    def record(
        receipt: str = typer.Option(..., "--receipt", help="Decision receipt id (trust.ev.NNNNNN)."),
        status: str = typer.Option(..., "--status", help="success | failure | error"),
        cost: int = typer.Option(0, "--cost", help="Actual cost units spent."),
        note: str | None = typer.Option(None, "--note"),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.trust_loop_runtime import ExecutionOutcome, ExecutionStatus

        try:
            parsed_status = ExecutionStatus(status)
        except ValueError:
            raise typer.BadParameter("status must be success, failure, or error")
        outcome_record_id = state_for_home(home).build_engine().record(
            receipt,
            ExecutionOutcome(status=parsed_status, cost_actual_units=max(cost, 0), notes=note),
        )
        echo_json({"outcome_record_id": outcome_record_id, "caused_by": receipt})


def _resolved_zeus_bin() -> str:
    found = shutil.which("zeus")
    if found is not None:
        return str(Path(found).resolve())
    candidate = Path(sys.argv[0])
    if candidate.name == "zeus":
        return str(candidate.resolve())
    return "zeus"


def _hermes_preflight(*, port: int, home: Path | None) -> dict:
    import urllib.error
    import urllib.request

    from zeus_agent import __version__

    state = state_for_home(home)
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
    canary = _hermes_hook_canary(home=home)
    return {
        "zeus_version": __version__,
        "checks": {
            "control_plane_home": {"ok": home_ready, "path": str(state.root)},
            "hook_canary": canary,
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
        "(zeus init --home <new>) - a dogfood ledger with synthetic/early-bridge "
        "records is not clean soak evidence. Record hermes + zeus versions first.",
        "ready": home_ready and proxy_ok,
    }


def _hermes_hook_canary(*, home: Path | None) -> dict[str, object]:
    from zeus_agent.adapters.hermes import HermesGate

    output = HermesGate(state_for_home(home).build_engine()).pre_tool_call(
        {"session_id": "zeus.connect.canary", "tool": "read_file", "args": {"path": "/tmp/zeus-canary.txt"}}
    )
    receipt_id = output.get("receipt_id")
    return {
        "ok": output.get("action") == "allow" and isinstance(receipt_id, str),
        "receipt_id": receipt_id,
        "capability_id": output.get("capability_id"),
    }
