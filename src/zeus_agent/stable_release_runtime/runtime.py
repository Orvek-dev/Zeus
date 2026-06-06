from __future__ import annotations

from typing import Final

from zeus_agent.goal_intelligence_runtime import build_goal_intelligence_contract
from zeus_agent.installable_live_platform_runtime import build_installable_live_platform_contract
from zeus_agent.production_scale_platform_runtime import build_production_scale_platform_contract
from zeus_agent.stable_release_runtime.models import StableReleaseContract

_TARGET_VERSION: Final = "v3.0.0"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v3.0.0.stable_live_agent_platform"
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "token=",
    "private_key",
    "-----begin",
)


def build_stable_release_contract(*, raw_release_note: str = "") -> StableReleaseContract:
    raw_secret_marker_detected = _has_secret_marker(raw_release_note)
    blocked_reasons = ("raw_secret_marker_detected",) if raw_secret_marker_detected else ()
    goal = build_goal_intelligence_contract(scenario="status").to_payload()
    installable = build_installable_live_platform_contract(scenario="status").to_payload()
    scale = build_production_scale_platform_contract(scenario="status").to_payload()
    goal_ready = goal["decision"] == "report"
    installable_ready = installable["decision"] == "report" and bool(installable["installable_live_platform_ready"])
    scale_ready = scale["decision"] == "report" and bool(scale["production_scale_platform_ready"])
    ready = goal_ready and installable_ready and scale_ready and not blocked_reasons
    result = StableReleaseContract(
        decision="report" if ready else "blocked",
        target_version=_TARGET_VERSION,
        release_stage="zeus_stable_live_agent_platform",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        blocked_reasons=blocked_reasons if ready else _ready_blockers(
            blocked_reasons=blocked_reasons,
            goal_ready=goal_ready,
            installable_ready=installable_ready,
            scale_ready=scale_ready,
        ),
        stable_release_ready=ready,
        governed_live_platform_ready=ready,
        stable_public_release_ready=ready,
        goal_intelligence_platform_ready=goal_ready,
        installable_live_platform_ready=installable_ready,
        production_scale_platform_ready=scale_ready,
        plugin_ecosystem_available=True,
        remote_sandbox_policy_available=True,
        tenant_auth_contract_available=True,
        learning_ops_contract_available=True,
        candidate_only_learning_available=True,
        persistent_audit_contract_available=True,
        production_live_ready=False,
        unrestricted_live_execution_enabled=False,
        provider_live_api_available=True,
        mcp_live_server_available=True,
        gateway_live_delivery_available=True,
        sandbox_terminal_live_available=True,
        memory_privacy_live_available=True,
        provider_live_optin_available=True,
        provider_owned_client_live_available=True,
        mcp_owned_client_live_available=True,
        mcp_resources_enabled=False,
        mcp_prompts_enabled=False,
        external_gateway_production_enabled=False,
        browser_live_execution_enabled=False,
        remote_sandbox_execution_enabled=False,
        unattended_execution_enabled=False,
        raw_secret_marker_detected=raw_secret_marker_detected,
        credential_material_accessed=False,
        network_opened=False,
        external_delivery_opened=False,
        handler_executed=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _ready_blockers(
    *,
    blocked_reasons: tuple[str, ...],
    goal_ready: bool,
    installable_ready: bool,
    scale_ready: bool,
) -> tuple[str, ...]:
    reasons = list(blocked_reasons)
    if not goal_ready:
        reasons.append("goal_intelligence_platform_not_ready")
    if not installable_ready:
        reasons.append("installable_live_platform_not_ready")
    if not scale_ready:
        reasons.append("production_scale_platform_not_ready")
    return tuple(dict.fromkeys(reasons))


def _has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
