from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.objective_card_runtime import compile_from_frame
from zeus_agent.objective_frame_runtime import parse_frame, produce_frame


def register_objective_commands(app: typer.Typer) -> None:
    @app.command("objective")
    def objective(
        utterance: str = typer.Option(..., "--utterance", "-u", help="Plain-language goal."),
        frame_output: Optional[str] = typer.Option(
            None,
            "--frame-output",
            help="Raw cognitive-layer (LLM) output to compile, for deterministic/no-network use.",
        ),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        """Compile a plain-language goal into a governed objective card.

        With --frame-output, the supplied LLM output is parsed and compiled (no
        network). Without it, this surface reports that a cognitive provider must
        be wired — Zeus does not fabricate a frame from keywords.
        """
        if frame_output is not None:
            result = parse_frame(frame_output)
        else:
            result = produce_frame(utterance=utterance, generate=_no_provider)
        if not result.ok or result.frame is None:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": [result.blocked_reason or "frame_unavailable"],
                    "no_secret_echo": result.no_secret_echo,
                },
                as_json=as_json,
            )
            return
        card = compile_from_frame(result.frame)
        _print_payload(card.to_payload(), as_json=as_json)


def _no_provider(_prompt: str) -> str:
    # No cognitive provider wired in the bare CLI: fail closed and honest rather
    # than inventing a frame. A wired session injects a real GenerateFn.
    return ""


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
