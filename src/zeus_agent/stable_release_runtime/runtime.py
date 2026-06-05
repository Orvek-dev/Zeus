from __future__ import annotations

from typing import Final

from zeus_agent.stable_release_runtime.models import StableReleaseContract

_TARGET_VERSION: Final = "v1.0.0"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.0.0.stable_governed_live_platform"
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
    ready = not blocked_reasons
    result = StableReleaseContract(
        decision="report" if ready else "blocked",
        target_version=_TARGET_VERSION,
        release_stage="stable_governed_live_platform",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        blocked_reasons=blocked_reasons,
        stable_release_ready=ready,
        governed_live_platform_ready=ready,
        stable_public_release_ready=ready,
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


def _has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
