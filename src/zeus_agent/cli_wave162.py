from __future__ import annotations

import json

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewResult
from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewRuntime
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleRuntime
from zeus_agent.live_research_workflow_bundle_runtime import LiveResearchWorkflowBundleResult
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusRuntime
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusResult
from zeus_agent.live_research_workflow_authorization_runtime import (
    LiveResearchWorkflowAuthorizationResult,
    LiveResearchWorkflowAuthorizationRuntime,
)
from zeus_agent.live_research_workflow_executor_release_runtime import (
    LiveResearchWorkflowExecutorReleaseRuntime,
)
from zeus_agent.live_research_workflow_preflight_plan_runtime import LiveResearchWorkflowPreflightPlanRuntime
from zeus_agent.live_research_workflow_preflight_plan_runtime import LiveResearchWorkflowPreflightPlanResult
from zeus_agent.live_research_workflow_runbook_runtime import LiveResearchWorkflowRunbookResult
from zeus_agent.live_research_workflow_runbook_runtime import LiveResearchWorkflowRunbookRuntime
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowResult


def register_wave162_commands(app: typer.Typer) -> None:
    @app.command("live-research-workflow-bundle")
    def live_research_workflow_bundle(
        workflow_json: str = typer.Option(..., "--workflow-json"),
        bundle_ref: str = typer.Option(..., "--bundle-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            workflow = LiveResearchWorkflowResult.model_validate_json(workflow_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "bundle_ref": bundle_ref,
                    "blocked_reasons": ["malformed_live_research_workflow_bundle"],
                    "error": str(exc),
                    "network_opened": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowBundleRuntime().build(workflow=workflow, bundle_ref=bundle_ref)
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("live-research-workflow-bundle-status")
    def live_research_workflow_bundle_status(
        bundle_json: str = typer.Option(..., "--bundle-json"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            bundle = LiveResearchWorkflowBundleResult.model_validate_json(bundle_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "blocked_reasons": ["malformed_live_research_workflow_bundle_status"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowBundleStatusRuntime().build(bundle=bundle)
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("live-research-workflow-bundle-review")
    def live_research_workflow_bundle_review(
        bundle_json: str = typer.Option(..., "--bundle-json"),
        status_json: str = typer.Option(..., "--status-json"),
        review_ref: str = typer.Option(..., "--review-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            bundle = LiveResearchWorkflowBundleResult.model_validate_json(bundle_json)
            status = LiveResearchWorkflowBundleStatusResult.model_validate_json(status_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "review_ref": review_ref,
                    "blocked_reasons": ["malformed_live_research_workflow_bundle_review"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowBundleReviewRuntime().review(
            bundle=bundle,
            status=status,
            review_ref=review_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("live-research-workflow-runbook")
    def live_research_workflow_runbook(
        review_json: str = typer.Option(..., "--review-json"),
        runbook_ref: str = typer.Option(..., "--runbook-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            review = LiveResearchWorkflowBundleReviewResult.model_validate_json(review_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "runbook_ref": runbook_ref,
                    "blocked_reasons": ["malformed_live_research_workflow_runbook"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowRunbookRuntime().build(
            review=review,
            runbook_ref=runbook_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("live-research-workflow-preflight-plan")
    def live_research_workflow_preflight_plan(
        runbook_json: str = typer.Option(..., "--runbook-json"),
        preflight_ref: str = typer.Option(..., "--preflight-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            runbook = LiveResearchWorkflowRunbookResult.model_validate_json(runbook_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "preflight_ref": preflight_ref,
                    "blocked_reasons": ["malformed_live_research_workflow_preflight_plan"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowPreflightPlanRuntime().build(
            runbook=runbook,
            preflight_ref=preflight_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("live-research-workflow-authorization")
    def live_research_workflow_authorization(
        preflight_plan_json: str = typer.Option(..., "--preflight-plan-json"),
        authorization_ref: str = typer.Option(..., "--authorization-ref"),
        operator_approval_ref: str = typer.Option(..., "--operator-approval-ref"),
        evidence_ref: str = typer.Option(..., "--evidence-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            preflight_plan = LiveResearchWorkflowPreflightPlanResult.model_validate_json(
                preflight_plan_json
            )
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "authorization_ref": authorization_ref,
                    "blocked_reasons": ["malformed_live_research_workflow_authorization"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowAuthorizationRuntime().authorize(
            preflight_plan=preflight_plan,
            authorization_ref=authorization_ref,
            operator_approval_ref=operator_approval_ref,
            evidence_ref=evidence_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("live-research-workflow-executor-release")
    def live_research_workflow_executor_release(
        authorization_json: str = typer.Option(..., "--authorization-json"),
        release_ref: str = typer.Option(..., "--release-ref"),
        idempotency_key: str = typer.Option(..., "--idempotency-key"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            authorization = LiveResearchWorkflowAuthorizationResult.model_validate_json(authorization_json)
        except ValidationError as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "release_ref": release_ref,
                    "blocked_reasons": ["malformed_live_research_workflow_executor_release"],
                    "error": str(exc),
                    "network_opened": False,
                    "credential_material_accessed": False,
                    "live_production_claimed": False,
                    "no_secret_echo": True,
                },
                as_json=as_json,
            )
            return
        result = LiveResearchWorkflowExecutorReleaseRuntime().release(
            authorization=authorization,
            release_ref=release_ref,
            idempotency_key=idempotency_key,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
