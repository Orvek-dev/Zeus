from __future__ import annotations

import json
from typing import Optional

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_execution_bundle_review_runtime import LiveExecutionBundleReviewResult
from zeus_agent.live_execution_bundle_runtime import LiveExecutionBundleResult
from zeus_agent.live_execution_status_runtime import LiveExecutionStatusRuntime


def register_wave136_commands(app: typer.Typer) -> None:
    @app.command("live-execution-status")
    def live_execution_status(
        bundle_json: Optional[str] = typer.Option(None, "--bundle-json"),
        review_json: Optional[str] = typer.Option(None, "--review-json"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            bundle = _bundle(bundle_json)
            review = _review(review_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_execution_status",
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveExecutionStatusRuntime().build(bundle=bundle, review=review)
        _print_payload(result.to_payload(), as_json=as_json)


def _bundle(raw: Optional[str]) -> Optional[LiveExecutionBundleResult]:
    if raw is None:
        return None
    return LiveExecutionBundleResult.model_validate_json(raw)


def _review(raw: Optional[str]) -> Optional[LiveExecutionBundleReviewResult]:
    if raw is None:
        return None
    return LiveExecutionBundleReviewResult.model_validate_json(raw)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
