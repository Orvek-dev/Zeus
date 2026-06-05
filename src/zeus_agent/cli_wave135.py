from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_execution_bundle_review_runtime import LiveExecutionBundleReviewRuntime
from zeus_agent.live_execution_bundle_runtime import LiveExecutionBundleResult


def register_wave135_commands(app: typer.Typer) -> None:
    @app.command("live-execution-bundle-review")
    def live_execution_bundle_review(
        bundle_json: str = typer.Option(..., "--bundle-json"),
        reviewer_id: str = typer.Option(..., "--reviewer-id"),
        producer_id: str = typer.Option(..., "--producer-id"),
        evidence_id: list[str] = typer.Option([], "--evidence-id"),
        risk_ack: list[str] = typer.Option([], "--risk-ack"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            bundle = LiveExecutionBundleResult.model_validate_json(bundle_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_execution_bundle_review",
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveExecutionBundleReviewRuntime().review(
            bundle=bundle,
            reviewer_id=reviewer_id,
            producer_id=producer_id,
            evidence_ids=tuple(evidence_id),
            risk_acknowledgements=tuple(risk_ack),
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
