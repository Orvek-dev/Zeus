from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.objective_card_runtime import ObjectiveFrameInput, compile_from_frame

# Demo frames let a user try the surface with no LLM and no network. The compiler
# itself holds zero domain knowledge; these are sample cognitive-layer outputs,
# the same idea as the fake-provider scenarios elsewhere in Zeus.
_DEMO_FRAMES: dict[str, dict[str, JsonValue]] = {
    "blog": {
        "normalized_objective": "Automate my blog with AI",
        "triage": "automation",
        "budget_cap_units": 20,
        "projected_runs": 8,
        "required_criteria": ["topic_chosen", "post_written"],
        "unknowns": [
            {"unknown_id": "publish_target", "description": "Where should posts publish?",
             "risk_class": "external"},
            {"unknown_id": "spend_cap", "description": "What is the monthly budget cap?",
             "risk_class": "cost"},
            {"unknown_id": "frequency", "description": "How often to publish?", "risk_class": "time",
             "blast_radius": "account", "cost_bucket": 2, "failure_probability": 0.4,
             "safe_default": {"value": "twice weekly", "rationale": "conservative"}},
            {"unknown_id": "tone", "description": "What tone and length?", "risk_class": "quality",
             "sample_learnable": True},
        ],
        "candidates": [
            {
                "candidate_id": "blog.gated",
                "nodes": [
                    {"node_id": "research", "kind": "llm_generic", "cost_units": 2,
                     "produces_criteria": ["topic_chosen"]},
                    {"node_id": "check_topic", "kind": "verification",
                     "verifies_criteria": ["topic_chosen"]},
                    {"node_id": "draft", "kind": "llm_generic", "cost_units": 3,
                     "produces_criteria": ["post_written"]},
                    {"node_id": "critic", "kind": "verification", "verifies_criteria": ["post_written"]},
                    {"node_id": "approve", "kind": "approval_gate"},
                    {"node_id": "publish", "kind": "capability", "capability_ref": "mcp.blog.publish",
                     "side_effect": "public_write", "cost_units": 1},
                ],
                "edges": [
                    {"src": "research", "dst": "check_topic"},
                    {"src": "check_topic", "dst": "draft"},
                    {"src": "draft", "dst": "critic"},
                    {"src": "critic", "dst": "approve"},
                    {"src": "approve", "dst": "publish"},
                ],
            }
        ],
    },
    "tidy": {
        "normalized_objective": "Tidy my downloads folder",
        "triage": "oneshot",
        "required_criteria": ["scanned"],
        "unknowns": [
            {"unknown_id": "target_folder", "description": "Which folder?", "risk_class": "external",
             "blast_radius": "local", "irreversibility": "medium",
             "safe_default": {"value": "~/Downloads", "rationale": "named in request"}},
        ],
        "candidates": [
            {
                "candidate_id": "tidy.gated",
                "nodes": [
                    {"node_id": "scan", "kind": "llm_generic", "produces_criteria": ["scanned"]},
                    {"node_id": "check", "kind": "verification", "verifies_criteria": ["scanned"]},
                    {"node_id": "approve", "kind": "approval_gate"},
                    {"node_id": "move", "kind": "capability", "capability_ref": "builtin.fs.move",
                     "side_effect": "local_write"},
                ],
                "edges": [
                    {"src": "scan", "dst": "check"},
                    {"src": "check", "dst": "approve"},
                    {"src": "approve", "dst": "move"},
                ],
            }
        ],
    },
}


def register_objective_card_commands(app: typer.Typer) -> None:
    @app.command("objective-card")
    def objective_card(
        frame_json: Optional[str] = typer.Option(None, "--frame-json"),
        demo: Optional[str] = typer.Option(None, "--demo"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        """Compile a cognitive-layer frame into a governed objective card."""
        raw = _resolve_frame(frame_json=frame_json, demo=demo)
        if raw is None:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": ["missing_frame: pass --frame-json or --demo blog|tidy"],
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        try:
            frame = ObjectiveFrameInput.model_validate(raw)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": ["malformed_objective_frame"],
                    "error": str(exc),
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        card = compile_from_frame(frame)
        _print_payload(card.to_payload(), as_json=as_json)


def _resolve_frame(
    *,
    frame_json: Optional[str],
    demo: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if frame_json is not None:
        try:
            parsed = json.loads(frame_json)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    if demo is not None:
        return _DEMO_FRAMES.get(demo)
    return None


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
