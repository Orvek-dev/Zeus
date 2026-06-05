from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_research_status_runtime import LiveResearchStatusResult
from zeus_agent.live_research_workflow_authorization_runtime import LiveResearchWorkflowAuthorizationResult
from zeus_agent.live_research_workflow_execution_handoff_runtime import (
    LiveResearchWorkflowExecutionHandoffResult,
)
from zeus_agent.live_research_workflow_executor_release_runtime import (
    LiveResearchWorkflowExecutorReleaseResult,
)
from zeus_agent.live_research_workflow_loopback_executor_runtime import (
    LiveResearchWorkflowLoopbackExecutorResult,
)
from zeus_agent.live_research_workflow_execution_status_runtime import (
    LiveResearchWorkflowExecutionStatusResult,
)
from zeus_agent.live_research_workflow_execution_registry_runtime import (
    LiveResearchWorkflowExecutionRegistryResult,
)
from zeus_agent.live_research_workflow_external_preflight_runtime import (
    LiveResearchWorkflowExternalPreflightResult,
)
from zeus_agent.live_research_workflow_external_execution_runtime import (
    LiveResearchWorkflowExternalExecutionResult,
)
from zeus_agent.live_research_workflow_ontology_ingestion_runtime import (
    LiveResearchWorkflowOntologyIngestionResult,
)
from zeus_agent.live_research_workflow_ontology_registry_runtime import (
    LiveResearchWorkflowOntologyRegistryResult,
)
from zeus_agent.live_research_workflow_preflight_plan_runtime import LiveResearchWorkflowPreflightPlanResult
from zeus_agent.live_research_workflow_bundle_review_runtime import LiveResearchWorkflowBundleReviewResult
from zeus_agent.live_research_workflow_bundle_status_runtime import LiveResearchWorkflowBundleStatusResult
from zeus_agent.live_research_workflow_runbook_runtime import LiveResearchWorkflowRunbookResult
from zeus_agent.live_research_workflow_runtime import LiveResearchWorkflowResult


def register_wave41_commands(app: typer.Typer) -> None:
    @app.command("live")
    def live(
        include_smoke: bool = typer.Option(False, "--include-smoke"),
        scenario: str = typer.Option("happy", "--scenario"),
        research_status_json: Optional[str] = typer.Option(None, "--research-status-json"),
        research_workflow_json: Optional[str] = typer.Option(None, "--research-workflow-json"),
        research_workflow_bundle_status_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-bundle-status-json",
        ),
        research_workflow_bundle_review_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-bundle-review-json",
        ),
        research_workflow_runbook_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-runbook-json",
        ),
        research_workflow_preflight_plan_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-preflight-plan-json",
        ),
        research_workflow_authorization_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-authorization-json",
        ),
        research_workflow_executor_release_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-executor-release-json",
        ),
        research_workflow_execution_handoff_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-execution-handoff-json",
        ),
        research_workflow_loopback_executor_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-loopback-executor-json",
        ),
        research_workflow_execution_status_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-execution-status-json",
        ),
        research_workflow_execution_registry_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-execution-registry-json",
        ),
        research_workflow_external_preflight_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-external-preflight-json",
        ),
        research_workflow_external_execution_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-external-execution-json",
        ),
        research_workflow_ontology_ingestion_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-ontology-ingestion-json",
        ),
        research_workflow_ontology_registry_json: Optional[str] = typer.Option(
            None,
            "--research-workflow-ontology-registry-json",
        ),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        if scenario not in {"happy", "blocked"}:
            raise typer.BadParameter("scenario must be one of: happy, blocked")
        research_status = _research_status(research_status_json)
        research_workflow = _research_workflow(research_workflow_json)
        research_workflow_bundle_status = _research_workflow_bundle_status(research_workflow_bundle_status_json)
        research_workflow_bundle_review = _research_workflow_bundle_review(research_workflow_bundle_review_json)
        research_workflow_runbook = _research_workflow_runbook(research_workflow_runbook_json)
        research_workflow_preflight_plan = _research_workflow_preflight_plan(research_workflow_preflight_plan_json)
        research_workflow_authorization = _research_workflow_authorization(research_workflow_authorization_json)
        research_workflow_executor_release = _research_workflow_executor_release(
            research_workflow_executor_release_json
        )
        research_workflow_execution_handoff = _research_workflow_execution_handoff(
            research_workflow_execution_handoff_json
        )
        research_workflow_loopback_executor = _research_workflow_loopback_executor(
            research_workflow_loopback_executor_json
        )
        research_workflow_execution_status = _research_workflow_execution_status(
            research_workflow_execution_status_json
        )
        research_workflow_execution_registry = _research_workflow_execution_registry(
            research_workflow_execution_registry_json
        )
        research_workflow_external_preflight = _research_workflow_external_preflight(
            research_workflow_external_preflight_json
        )
        research_workflow_external_execution = _research_workflow_external_execution(
            research_workflow_external_execution_json
        )
        research_workflow_ontology_ingestion = _research_workflow_ontology_ingestion(
            research_workflow_ontology_ingestion_json
        )
        research_workflow_ontology_registry = _research_workflow_ontology_registry(
            research_workflow_ontology_registry_json
        )
        result = LiveCockpitRuntime(home or default_zeus_home()).build(
            include_smoke=include_smoke,
            scenario=scenario,
            research_status=research_status,
            research_workflow=research_workflow,
            research_workflow_bundle_status=research_workflow_bundle_status,
            research_workflow_bundle_review=research_workflow_bundle_review,
            research_workflow_runbook=research_workflow_runbook,
            research_workflow_preflight_plan=research_workflow_preflight_plan,
            research_workflow_authorization=research_workflow_authorization,
            research_workflow_executor_release=research_workflow_executor_release,
            research_workflow_execution_handoff=research_workflow_execution_handoff,
            research_workflow_loopback_executor=research_workflow_loopback_executor,
            research_workflow_execution_status=research_workflow_execution_status,
            research_workflow_execution_registry=research_workflow_execution_registry,
            research_workflow_external_preflight=research_workflow_external_preflight,
            research_workflow_external_execution=research_workflow_external_execution,
            research_workflow_ontology_ingestion=research_workflow_ontology_ingestion,
            research_workflow_ontology_registry=research_workflow_ontology_registry,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _research_status(raw: Optional[str]) -> Optional[LiveResearchStatusResult]:
    if raw is None:
        return None
    return LiveResearchStatusResult.model_validate_json(raw)


def _research_workflow(raw: Optional[str]) -> Optional[LiveResearchWorkflowResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowResult.model_validate_json(raw)


def _research_workflow_bundle_status(raw: Optional[str]) -> Optional[LiveResearchWorkflowBundleStatusResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowBundleStatusResult.model_validate_json(raw)


def _research_workflow_bundle_review(raw: Optional[str]) -> Optional[LiveResearchWorkflowBundleReviewResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowBundleReviewResult.model_validate_json(raw)


def _research_workflow_runbook(raw: Optional[str]) -> Optional[LiveResearchWorkflowRunbookResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowRunbookResult.model_validate_json(raw)


def _research_workflow_preflight_plan(raw: Optional[str]) -> Optional[LiveResearchWorkflowPreflightPlanResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowPreflightPlanResult.model_validate_json(raw)


def _research_workflow_authorization(raw: Optional[str]) -> Optional[LiveResearchWorkflowAuthorizationResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowAuthorizationResult.model_validate_json(raw)


def _research_workflow_executor_release(raw: Optional[str]) -> Optional[LiveResearchWorkflowExecutorReleaseResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowExecutorReleaseResult.model_validate_json(raw)


def _research_workflow_execution_handoff(raw: Optional[str]) -> Optional[LiveResearchWorkflowExecutionHandoffResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowExecutionHandoffResult.model_validate_json(raw)


def _research_workflow_loopback_executor(raw: Optional[str]) -> Optional[LiveResearchWorkflowLoopbackExecutorResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowLoopbackExecutorResult.model_validate_json(raw)


def _research_workflow_execution_status(raw: Optional[str]) -> Optional[LiveResearchWorkflowExecutionStatusResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowExecutionStatusResult.model_validate_json(raw)


def _research_workflow_execution_registry(raw: Optional[str]) -> Optional[LiveResearchWorkflowExecutionRegistryResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowExecutionRegistryResult.model_validate_json(raw)


def _research_workflow_external_preflight(raw: Optional[str]) -> Optional[LiveResearchWorkflowExternalPreflightResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowExternalPreflightResult.model_validate_json(raw)


def _research_workflow_external_execution(raw: Optional[str]) -> Optional[LiveResearchWorkflowExternalExecutionResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowExternalExecutionResult.model_validate_json(raw)


def _research_workflow_ontology_ingestion(
    raw: Optional[str],
) -> Optional[LiveResearchWorkflowOntologyIngestionResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowOntologyIngestionResult.model_validate_json(raw)


def _research_workflow_ontology_registry(
    raw: Optional[str],
) -> Optional[LiveResearchWorkflowOntologyRegistryResult]:
    if raw is None:
        return None
    return LiveResearchWorkflowOntologyRegistryResult.model_validate_json(raw)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
