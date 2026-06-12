from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from zeus_agent.live_connection_runtime import (
    LiveConnectionOrchestraPlanner,
    LiveConnectionRequest,
)
from zeus_agent.orchestration_runtime import ParallelTaskSpec
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.wave14_orchestra_scenarios import wave14_orchestra_plan_payload


def _lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave14.lease.orchestra_test",
        objective_id="wave14.objective.live_connection",
        principal_id="wave14.principal.orchestra_test",
        run_id="wave14.run.orchestra_test",
        allowed_capabilities=("provider.external.plan",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.local",),
        budget_limit=10_000,
        evidence_target="mneme.wave14.live_connection",
        live_transport_allowed=False,
        issued_at=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
    )


def _task() -> ParallelTaskSpec:
    return ParallelTaskSpec(
        task_id="orchestra-test",
        owned_paths=("src/zeus_agent/live_connection_runtime",),
        evidence_target="mneme.wave14.live_connection",
        live_capable=False,
    )


def _request(
    *,
    request_id: str = "wave14.req.provider",
    evidence_target: str = "mneme.wave14.live_connection",
) -> LiveConnectionRequest:
    return LiveConnectionRequest(
        request_id=request_id,
        surface_kind="provider",
        capability_id="provider.external.plan",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        evidence_target=evidence_target,
    )


def test_wave14_orchestra_plans_parallel_live_connection_without_execution(
    tmp_path: Path,
) -> None:
    payload = wave14_orchestra_plan_payload(tmp_path / "wave14-state")

    assert payload["scenario_id"] == "G004"
    assert payload["orchestra_decision"] == "planned"
    assert payload["parallel_schedule_decision"] == "planned"
    assert payload["live_plan_decision"] == "planned"
    assert payload["wave_count"] == 2
    assert set(payload["planned_surface_kinds"]) >= {
        "provider",
        "mcp",
        "github",
        "browser",
        "terminal",
    }
    assert payload["trace_step_count"] == 2
    assert payload["cleanup_obligation_required"] is True
    assert payload["replay_available"] is False
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert payload["live_production_claimed"] is False


def test_wave14_orchestra_blocks_route_with_replay_without_secret_echo(
    tmp_path: Path,
) -> None:
    payload = wave14_orchestra_plan_payload(
        tmp_path / "wave14-state",
        scenario="blocked-route",
    )
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["orchestra_decision"] == "blocked"
    assert payload["parallel_schedule_decision"] == "planned"
    assert payload["live_plan_decision"] == "blocked"
    assert payload["replay_available"] is True
    assert "missing_lease" in payload["blocked_reasons"]
    assert "mcp_prompt_injection" in payload["blocked_reasons"]
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert payload["raw_secret_present"] is False
    assert "sk-wave14-orchestra-secret" not in serialized


def test_wave14_orchestra_blocks_parallel_write_conflicts(tmp_path: Path) -> None:
    payload = wave14_orchestra_plan_payload(
        tmp_path / "wave14-state",
        scenario="blocked-schedule",
    )

    assert payload["orchestra_decision"] == "blocked"
    assert payload["parallel_schedule_decision"] == "blocked"
    assert payload["live_plan_decision"] == "blocked"
    assert payload["replay_available"] is True
    assert payload["cleanup_obligation_required"] is False
    assert payload["handler_executed"] is False
    assert payload["network_opened"] is False
    assert any(
        str(reason).startswith("owned_path_conflict:")
        for reason in payload["blocked_reasons"]
    )


def test_wave14_orchestra_blocks_expired_lease_and_evidence_scope_bypass() -> None:
    expired_lease = _lease().model_copy(
        update={
            "issued_at": datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
            "expires_at": datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc),
        },
    )

    expired = LiveConnectionOrchestraPlanner().plan(
        (_task(),),
        (_request(),),
        runtime_lease=expired_lease,
        objective_contract_bound=True,
        now=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
    )
    bypass = LiveConnectionOrchestraPlanner().plan(
        (_task(),),
        (_request(evidence_target="mneme.wave14.other_target"),),
        runtime_lease=_lease(),
        objective_contract_bound=True,
        now=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
    )

    assert expired.decision == "blocked"
    assert "runtime_lease_expired" in expired.blocked_reasons
    assert bypass.decision == "blocked"
    assert "evidence_scope_bypass" in bypass.blocked_reasons
    assert expired.handler_executed is False
    assert expired.network_opened is False
    assert bypass.handler_executed is False
    assert bypass.network_opened is False


def test_wave14_orchestra_redacts_secret_like_request_id() -> None:
    raw_secret = "sk-audit-route-secret"
    plan = LiveConnectionOrchestraPlanner().plan(
        (_task(),),
        (_request(request_id=raw_secret),),
        runtime_lease=_lease(),
        objective_contract_bound=True,
        now=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
    )
    serialized = plan.model_dump_json()

    assert plan.decision == "planned"
    assert plan.no_secret_echo is True
    assert plan.live_plan.routes[0].request_id == "redacted"
    assert raw_secret not in serialized


def test_wave14_orchestra_redacts_private_key_shaped_request_id() -> None:
    raw_pem = "-----BEGIN PRIVATE KEY-----abc123-----END PRIVATE KEY-----"
    raw_spaced_private_key = "private key:abc123"
    plans = tuple(
        LiveConnectionOrchestraPlanner().plan(
            (_task(),),
            (_request(request_id=raw_secret),),
            runtime_lease=_lease(),
            objective_contract_bound=True,
            now=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
        )
        for raw_secret in (raw_pem, raw_spaced_private_key)
    )
    serialized = json.dumps(
        [plan.model_dump(mode="json") for plan in plans],
        sort_keys=True,
    )

    assert all(plan.decision == "planned" for plan in plans)
    assert all(plan.no_secret_echo is True for plan in plans)
    assert all(plan.live_plan.routes[0].request_id == "redacted" for plan in plans)
    assert raw_pem not in serialized
    assert raw_spaced_private_key not in serialized


def test_wave14_orchestra_blocks_surface_capability_namespace_mismatch() -> None:
    request = LiveConnectionRequest(
        request_id="wave14.req.provider_mcp",
        surface_kind="provider",
        capability_id="mcp.server.plan",
    )
    lease = RuntimeLease(
        lease_id="wave14.lease.namespace_mismatch",
        objective_id="wave14.objective.live_connection",
        principal_id="wave14.principal.orchestra_test",
        run_id="wave14.run.namespace_mismatch",
        allowed_capabilities=("mcp.server.plan",),
        budget_limit=10_000,
        evidence_target="mneme.wave14.live_connection",
        issued_at=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
        expires_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
    )

    plan = LiveConnectionOrchestraPlanner().plan(
        (_task(),),
        (request,),
        runtime_lease=lease,
        objective_contract_bound=True,
        now=datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc),
    )

    assert plan.decision == "blocked"
    assert "runtime_kind_capability_mismatch" in plan.blocked_reasons
    assert plan.handler_executed is False
    assert plan.network_opened is False
