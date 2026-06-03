from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from pydantic import ValidationError

from zeus_agent.agent_runtime import run_wave2_loop
from zeus_agent.cli_wave3 import register_wave3_commands
from zeus_agent.cli_wave4 import register_wave4_commands
from zeus_agent.cli_wave5 import register_wave5_commands
from zeus_agent.cli_wave6 import register_wave6_commands
from zeus_agent.cli_wave7 import register_wave7_commands
from zeus_agent.cli_wave8 import register_wave8_commands
from zeus_agent.cli_wave9 import register_wave9_commands
from zeus_agent.cli_wave10 import register_wave10_commands
from zeus_agent.cli_wave11 import register_wave11_commands
from zeus_agent.cli_wave12 import register_wave12_commands
from zeus_agent.cli_wave13 import register_wave13_commands
from zeus_agent.cli_wave14 import register_wave14_commands
from zeus_agent.cli_total import register_total_commands
from zeus_agent.cli_final import register_final_commands
from zeus_agent.kernel.authority import AuthorityContext, CapabilityGrant, PathGrant
from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityRisk,
    SideEffect,
)

app = typer.Typer(
    no_args_is_help=True,
    help=(
        "Zeus Agent CLI. "
        "This surface exposes governed local runtime, provider, tool, transport, "
        "conversation, production scaffold, and final architecture checks."
    ),
)


@app.callback()
def main() -> None:
    return None


@app.command("kernel-status")
def kernel_status() -> None:
    typer.echo(
        "Zeus governed kernel is active. "
        "Use --help to inspect local runtime, provider, tool, transport, and eval commands."
    )


def _wave1_kernel_graph() -> CapabilityGraph:
    return CapabilityGraph(
        [
            CapabilityDescriptor(
                capability_id="file.read",
                name="file.read",
                risk=CapabilityRisk.low,
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                output_schema={"type": "object"},
                description="Read-only in-memory stub operation for Wave 1 kernel dump.",
            ),
            CapabilityDescriptor(
                capability_id="terminal.run",
                name="terminal.run",
                risk=CapabilityRisk.high,
                input_schema={"type": "object", "properties": {"cmd": {"type": "string"}}},
                output_schema={"type": "object"},
                side_effects=[SideEffect.local_process],
                description="Mutating local-process capability placeholder for Wave 1 checks.",
            ),
        ]
    )


def _default_authority_context(granted_capabilities: list[str]) -> AuthorityContext:
    path_grants = []
    if "file.read" in set(granted_capabilities):
        path_grants.append(PathGrant(capability_id="file.read", path_prefix="/virtual/"))
    return AuthorityContext(
        principal_id="wave1-principal",
        run_id="wave1-run",
        goal_contract_id="wave1-goal",
        capability_grants=[CapabilityGrant(capability_id=value) for value in granted_capabilities],
        path_grants=path_grants,
    )


def _load_authority_context(authority_json: Optional[str]) -> AuthorityContext:
    if authority_json is None:
        return _default_authority_context(["file.read"])
    parsed = json.loads(authority_json)
    return AuthorityContext.model_validate(parsed)


def _print_payload(payload: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))


@app.command("kernel-dump")
def kernel_dump(
    scenario: str = typer.Option(
        "approved-read",
        "--scenario",
        help=(
            "Wave 1 kernel dump scenario. "
            "Use approved-read or unapproved-terminal to inspect broker decisions."
        ),
    ),
    authority_json: Optional[str] = typer.Option(
        None,
        "--authority-json",
        help=(
            "Optional authority JSON override for Wave 1 kernel dump. "
            "Malformed or invalid authority input fails closed."
        ),
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON output for Wave 1 kernel dump.",
    ),
) -> None:
    if scenario not in {"approved-read", "unapproved-terminal"}:
        raise typer.BadParameter("scenario must be one of: approved-read, unapproved-terminal")

    try:
        authority = _load_authority_context(authority_json)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        error_payload = {
            "error": "invalid_authority_json: {0}".format(str(exc)),
            "principal_id": "invalid",
            "model_visible_capabilities": [],
            "allowed_capabilities": [],
        }
        _print_payload(error_payload, as_json=as_json)
        raise typer.Exit(code=1)

    graph = _wave1_kernel_graph()
    handler_marker = {"terminal_run_called": False}

    def read_handler(payload: dict[str, object]) -> dict[str, object]:
        return {"path": payload.get("path"), "content": "wave1_stub"}

    def terminal_handler(payload: dict[str, object]) -> dict[str, object]:
        handler_marker["terminal_run_called"] = True
        return {"accepted": bool(payload)}

    broker = CapabilityBroker(
        graph=graph,
        handlers={"file.read": read_handler, "terminal.run": terminal_handler},
    )
    capability_id = "file.read" if scenario == "approved-read" else "terminal.run"
    payload = {"path": "/virtual/wave1.txt"} if capability_id == "file.read" else {"cmd": "echo noop"}
    response = broker.dispatch(capability_id=capability_id, payload=payload, context=authority)

    visible = graph.compile_model_schema(
        profile="coding-agent",
        authority=authority,
        approval_receipts=None,
    )
    visible_names = [entry["function"]["name"] for entry in visible]
    blocked_capabilities = [
        value for value in ["file.read", "terminal.run"] if value not in set(visible_names)
    ]
    output = {
        "scenario": scenario,
        "model_visible_capabilities": visible_names,
        "blocked_capabilities": blocked_capabilities,
        "allowed_capabilities": [value for value in ["file.read", "terminal.run"] if value not in blocked_capabilities],
        "decision": response["decision"],
        "capability_id": response["capability_id"],
        "result": response.get("result"),
        "reason": response.get("reason"),
        "evidence": response["evidence"],
        "handler_executed": handler_marker["terminal_run_called"],
    }
    _print_payload(output, as_json=as_json)


@app.command("wave2-loop")
def wave2_loop(
    scenario: str = typer.Option(
        "happy",
        "--scenario",
        help="Wave 2 fake local loop scenario. Use happy or blocked.",
    ),
    home: Optional[Path] = typer.Option(
        None,
        "--home",
        help="Optional local state home for the SQLite fake loop database.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON output for the Wave 2 fake loop.",
    ),
) -> None:
    if scenario not in {"happy", "blocked"}:
        raise typer.BadParameter("scenario must be one of: happy, blocked")
    state_home = home if home is not None else Path(tempfile.mkdtemp(prefix="zeus-wave2-"))
    payload = run_wave2_loop(scenario=scenario, home=state_home)
    _print_payload(payload, as_json=as_json)

register_wave3_commands(app)
register_wave4_commands(app)
register_wave5_commands(app)
register_wave6_commands(app)
register_wave7_commands(app)
register_wave8_commands(app)
register_wave9_commands(app)
register_wave10_commands(app)
register_wave11_commands(app)
register_wave12_commands(app)
register_wave13_commands(app)
register_wave14_commands(app)
register_total_commands(app)
register_final_commands(app)
