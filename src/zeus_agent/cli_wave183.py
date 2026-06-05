from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffResult,
)
from zeus_agent.live_research_workflow_external_preflight_runtime import (
    LiveResearchWorkflowExternalPreflightRuntime,
)


def register_wave183_commands(app: typer.Typer) -> None:
    @app.command("live-research-workflow-external-preflight")
    def live_research_workflow_external_preflight(
        handoff_json: str = typer.Option(..., "--handoff-json"),
        policy_json: str = typer.Option(..., "--policy-json"),
        preflight_ref: str = typer.Option(..., "--preflight-ref"),
        external_execution_ref: str = typer.Option(..., "--external-execution-ref"),
        operator_approval_ref: str = typer.Option(..., "--operator-approval-ref"),
        evidence_ref: str = typer.Option(..., "--evidence-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            handoff = LiveResearchWorkflowExecutionHandoffResult.model_validate_json(handoff_json)
            policy = LiveResearchActivationPolicyResult.model_validate_json(policy_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": ["malformed_live_research_workflow_external_preflight"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowExternalPreflightRuntime().build(
            handoff=handoff,
            policy=policy,
            preflight_ref=preflight_ref,
            external_execution_ref=external_execution_ref,
            operator_approval_ref=operator_approval_ref,
            evidence_ref=evidence_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
