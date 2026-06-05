from __future__ import annotations

from pydantic import JsonValue


def recommended_next_commands(*, include_smoke: bool) -> tuple[str, ...]:
    commands = [
        "zeus live-profile --json",
        "zeus approval-receipt --json",
        "zeus live-preflight --json",
        "zeus live-handoff --json",
        "zeus live-execute-plan --json",
        "zeus live-readiness",
        "zeus live-optin-smoke --scenario happy",
        "zeus live-research-status --json",
        "zeus live-research-workflow --json",
        "zeus live-research-workflow-bundle-status --json",
        "zeus live-research-workflow-bundle-review --json",
        "zeus live-research-workflow-runbook --json",
        "zeus live-research-workflow-preflight-plan --json",
        "zeus live-research-workflow-authorization --json",
        "zeus live-research-workflow-executor-release --json",
        "zeus live-research-workflow-execution-handoff --json",
        "zeus live-research-workflow-loopback-executor --json",
        "zeus live-research-workflow-execution-status --json",
        "zeus live-research-workflow-execution-records --json",
        "zeus live-research-workflow-external-preflight --json",
        "zeus live-research-workflow-external-execution --json",
        "zeus live-research-workflow-ontology-ingestion --json",
        "zeus live-research-workflow-ontology-record --json",
        "zeus doctor",
        "zeus setup --provider",
    ]
    if not include_smoke:
        commands.insert(0, "zeus live --include-smoke --scenario happy")
    return tuple(commands)


def activation_pipeline() -> tuple[dict[str, JsonValue], ...]:
    return (
        _pipeline_stage(
            stage_id="live_profile",
            command="zeus live-profile --json",
            purpose="compose live surface request and lease templates",
        ),
        _pipeline_stage(
            stage_id="approval_receipt",
            command="zeus approval-receipt --json",
            purpose="record local opt-in proof for a known approval gate",
        ),
        _pipeline_stage(
            stage_id="live_preflight",
            command="zeus live-preflight --json",
            purpose="validate receipt, lease, probe, source pin, cleanup, and beta activation",
        ),
        _pipeline_stage(
            stage_id="live_handoff",
            command="zeus live-handoff --json",
            purpose="create operator-reviewable handoff manifest",
        ),
        _pipeline_stage(
            stage_id="live_execute_plan",
            command="zeus live-execute-plan --json",
            purpose="produce dry-run execution plan and cleanup obligations",
        ),
    )


def _pipeline_stage(*, stage_id: str, command: str, purpose: str) -> dict[str, JsonValue]:
    return {
        "stage_id": stage_id,
        "command": command,
        "purpose": purpose,
        "operator_review_required": True,
        "execution_allowed": False,
        "network_opened": False,
        "handler_executed": False,
        "external_delivery_opened": False,
        "live_production_claimed": False,
    }
