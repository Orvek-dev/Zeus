from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from zeus_agent.doctor_runtime import doctor_report
from zeus_agent.entry_runtime import ZeusChatRuntime
from zeus_agent.mcp_runtime import curated_mcp_catalog_payload
from zeus_agent.orchestration_runtime import DynamicWorkflowCompiler, WorkflowCompileRequest
from zeus_agent.research_runtime import build_research_brief
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.setup_runtime import setup_plan
from zeus_agent.workflow_runtime import StandingOrderRequest, StandingOrderRuntime


def run_golden_journeys(*, home: Path) -> dict[str, Any]:
    journeys = (
        _first_chat(home),
        _setup_doctor(home),
        _mcp_catalog(),
        _adaptive_workflow(),
        _research_brief(),
        _cron_security_block(),
    )
    passed = [journey for journey in journeys if journey["status"] == "pass"]
    return {
        "journey_count": len(journeys),
        "passed_count": len(passed),
        "failed_count": len(journeys) - len(passed),
        "journeys": journeys,
        "network_opened": any(bool(item["network_opened"]) for item in journeys),
        "external_delivery_opened": any(bool(item["external_delivery_opened"]) for item in journeys),
        "live_production_claimed": any(bool(item["live_production_claimed"]) for item in journeys),
    }


def _first_chat(home: Path) -> dict[str, Any]:
    payload = ZeusChatRuntime(home).run_turn(
        message="hello Zeus",
        session_id="golden",
        provider_id="fake",
        profile="chat",
    ).to_payload()
    return _journey(
        "first_chat",
        payload["assistant_message"].startswith("Zeus is here") and payload["live_production_claimed"] is False,
        live_production_claimed=bool(payload["live_production_claimed"]),
    )


def _setup_doctor(home: Path) -> dict[str, Any]:
    setup = setup_plan(home=home, provider_id="fake", mcp=True, local=True)
    doctor = doctor_report(home)
    live_claim = bool(setup["live_production_claimed"]) or bool(doctor["live_production_claimed"])
    passed = setup["config_preview"]["provider_id"] == "fake" and not live_claim
    return _journey("setup_doctor", passed, live_production_claimed=live_claim)


def _mcp_catalog() -> dict[str, Any]:
    payload = curated_mcp_catalog_payload()
    passed = payload["catalog_entry_count"] == 25 and payload["beta_enabled_count"] == 10
    return _journey(
        "mcp_catalog",
        passed,
        network_opened=bool(payload["network_opened"]),
        live_production_claimed=bool(payload["live_production_claimed"]),
    )


def _adaptive_workflow() -> dict[str, Any]:
    plan = DynamicWorkflowCompiler().compile(
        WorkflowCompileRequest(
            objective="Implement provider, MCP catalog, cron, and review slices",
            task_count=5,
            requires_code=True,
            evidence_target="mneme.wave34.golden",
        )
    )
    return _journey(
        "adaptive_workflow",
        plan.decision == "compiled" and plan.selected_pattern == "fan_out_and_synthesize",
        network_opened=plan.network_opened,
        live_production_claimed=plan.live_production_claimed,
    )


def _research_brief() -> dict[str, Any]:
    payload = build_research_brief(
        objective_id="wave34.golden",
        query="parallel coding orchestration with source pins",
    )
    return _journey(
        "research_brief",
        payload["decision"] == "planned" and payload["external_claims_pinned"] is True,
        network_opened=bool(payload["network_opened"]),
        live_production_claimed=bool(payload["live_production_claimed"]),
    )


def _cron_security_block() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    result = StandingOrderRuntime().plan(
        request=StandingOrderRequest(
            standing_order_id="standing.golden.deploy",
            objective="deploy and notify channel",
            cron_expression="*/5 * * * *",
            idempotency_key="standing-golden-deploy",
            evidence_target="mneme.wave34.golden",
            destructive_action_requested=True,
            live_delivery_requested=True,
            delivery_targets=("slack://ops",),
        ),
        lease=RuntimeLease(
            lease_id="wave34.lease.cron",
            objective_id="wave34.objective.cron",
            principal_id="wave34.principal.operator",
            run_id="wave34.run.cron",
            allowed_capabilities=("cron.schedule.tick",),
            credential_scopes=("external.gateway.readonly",),
            network_hosts=("gateway.local",),
            budget_limit=100,
            evidence_target="mneme.wave34.golden",
            live_transport_allowed=False,
            issued_at=now,
            expires_at=now + timedelta(hours=1),
        ),
        now=now,
    )
    return _journey(
        "cron_security_block",
        result.decision == "blocked" and "headless_destructive_requires_approval" in result.reasons,
        network_opened=result.network_opened,
        external_delivery_opened=result.external_delivery_opened,
        live_production_claimed=result.live_production_claimed,
    )


def _journey(
    journey_id: str,
    passed: bool,
    *,
    network_opened: bool = False,
    external_delivery_opened: bool = False,
    live_production_claimed: bool = False,
) -> dict[str, Any]:
    return {
        "journey_id": journey_id,
        "status": "pass" if passed else "fail",
        "network_opened": network_opened,
        "external_delivery_opened": external_delivery_opened,
        "live_production_claimed": live_production_claimed,
    }


__all__ = ["run_golden_journeys"]
