from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.governed_objective_runtime import GovernedObjectiveOrchestrator
from zeus_agent.objective_card_runtime import ObjectiveFrameInput


def register_objective_run_commands(app: typer.Typer) -> None:
    @app.command("objective-run")
    def objective_run(
        frame_output: str = typer.Option(..., "--frame-output", help="Cognitive-layer frame JSON."),
        approve_gates: Optional[str] = typer.Option(
            None, "--approve-gates", help="Comma-separated gate node ids to approve and resume."
        ),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        """Run a governed objective end-to-end: frame → card → execute → evidence.

        Without --approve-gates a side-effecting plan suspends at its gate; pass
        the gate ids to approve and resume.
        """
        try:
            frame = ObjectiveFrameInput.model_validate_json(frame_output)
        except ValidationError as exc:
            _print_payload(
                {"decision": "blocked", "blocked_reasons": ["malformed_objective_frame"], "error": str(exc)},
                as_json=as_json,
            )
            return
        orch = GovernedObjectiveOrchestrator(home=home or default_zeus_home())
        result = orch.compile_and_run(frame)
        if result.stage == "waiting_approval" and approve_gates and result.run_id is not None:
            gates = tuple(g.strip() for g in approve_gates.split(",") if g.strip())
            result = orch.resume(result.run_id, approved_gates=gates)
        payload = result.to_payload()
        if result.run_id is not None:
            payload["evidence_timeline"] = orch.evidence_timeline(result.run_id)
        _print_payload(payload, as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
