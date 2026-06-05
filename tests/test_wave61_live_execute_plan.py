from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from zeus_agent import ZeusAgent
from zeus_agent.approval_receipt_runtime import ApprovalReceiptRuntime
from zeus_agent.live_execute_runtime import LiveExecutePlanRequest, LiveExecutePlanRuntime
from zeus_agent.live_handoff_runtime import LiveHandoffRequest, LiveHandoffRuntime
from zeus_agent.live_preflight_runtime import LivePreflightRequest, LivePreflightRuntime
from zeus_agent.runtime_lease import RuntimeLease


def test_live_execute_plan_dry_runs_ready_handoff_without_execution_permission() -> None:
    handoff = _ready_handoff()

    result = LiveExecutePlanRuntime().plan(
        LiveExecutePlanRequest(
            execution_id="wave61.execution.provider",
            handoff=handoff,
        ),
    )

    assert result.decision == "planned"
    assert result.execution_plan_id.startswith("live-execute-plan-")
    assert result.handoff_manifest_id == handoff.manifest_id
    assert result.execution_allowed is False
    assert result.dry_run is True
    assert "bind_approval_receipt" in result.planned_steps
    assert "write_execution_evidence" in result.cleanup_obligations
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.external_delivery_opened is False
    assert result.live_production_claimed is False


def test_live_execute_plan_blocks_live_execution_request() -> None:
    handoff = _ready_handoff()

    result = LiveExecutePlanRuntime().plan(
        LiveExecutePlanRequest(
            execution_id="wave61.execution.provider",
            handoff=handoff,
            execute_live=True,
        ),
    )

    assert result.decision == "blocked"
    assert "live_execution_requires_external_operator" in result.blocked_reasons
    assert result.execution_allowed is False
    assert result.network_opened is False


def test_live_execute_plan_blocks_non_ready_handoff() -> None:
    handoff = _blocked_handoff()

    result = LiveExecutePlanRuntime().plan(
        LiveExecutePlanRequest(
            execution_id="wave61.execution.provider",
            handoff=handoff,
        ),
    )

    assert result.decision == "blocked"
    assert "handoff_not_ready" in result.blocked_reasons
    assert result.execution_plan_id is None
    assert result.execution_allowed is False


def test_live_execute_plan_redacts_secret_like_confirmation() -> None:
    raw_secret = "sk-" + "wave61-secret"
    handoff = _ready_handoff()

    result = LiveExecutePlanRuntime().plan(
        LiveExecutePlanRequest(
            execution_id="wave61.execution.provider",
            handoff=handoff,
            operator_confirmation="confirm {0}".format(raw_secret),
        ),
    )
    serialized = result.model_dump_json()

    assert result.decision == "blocked"
    assert "secret_like_execution_field" in result.blocked_reasons
    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized
    assert result.no_secret_echo is True


def test_cli_exposes_live_execute_plan() -> None:
    handoff = _ready_handoff()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-execute-plan",
            "--request-json",
            LiveExecutePlanRequest(
                execution_id="wave61.execution.provider",
                handoff=handoff,
            ).model_dump_json(),
            "--json",
        ],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "planned"
    assert payload["execution_allowed"] is False
    assert payload["dry_run"] is True
    assert payload["live_production_claimed"] is False


def test_python_library_exposes_live_execute_plan() -> None:
    handoff = _ready_handoff()
    payload = ZeusAgent().live_execute_plan(
        LiveExecutePlanRequest(
            execution_id="wave61.execution.provider",
            handoff=handoff,
        ),
    )

    assert payload["decision"] == "planned"
    assert payload["execution_allowed"] is False
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def _ready_handoff():
    preflight = _preflight(source_pinned=True)
    return LiveHandoffRuntime().build(
        LiveHandoffRequest(
            handoff_id="wave61.handoff.provider",
            lease_id="wave61.lease.live",
            preflight=preflight,
        ),
    )


def _blocked_handoff():
    preflight = _preflight(source_pinned=False)
    return LiveHandoffRuntime().build(
        LiveHandoffRequest(
            handoff_id="wave61.handoff.provider",
            lease_id="wave61.lease.live",
            preflight=preflight,
        ),
    )


def _preflight(*, source_pinned: bool):
    receipt = ApprovalReceiptRuntime().record(
        approval_id="provider-live",
        principal_id="wave61.principal.operator",
        objective_id="wave61.objective.live",
        capability_id="provider.external.generate",
        now=_now(),
    )
    request = LivePreflightRequest(
        preflight_id="wave61.preflight.provider",
        approval_id="provider-live",
        principal_id="wave61.principal.operator",
        objective_id="wave61.objective.live",
        surface_kind="provider",
        surface_id="provider.external.openai",
        capability_id="provider.external.generate",
        evidence_target="mneme.wave61.live_execute",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        approval_receipt_id=receipt.receipt_id,
        approval_proof_hash=receipt.proof_hash,
        probe_healthy=True,
        source_pinned=source_pinned,
        cleanup_required=True,
    )
    return LivePreflightRuntime().evaluate(request, lease=_lease(), now=_now())


def _lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave61.lease.live",
        objective_id="wave61.objective.live",
        principal_id="wave61.principal.operator",
        run_id="wave61.run.live",
        allowed_capabilities=("provider.external.generate",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        budget_limit=100,
        evidence_target="mneme.wave61.live_execute",
        live_transport_allowed=True,
        issued_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc),
    )


def _now() -> datetime:
    return datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
