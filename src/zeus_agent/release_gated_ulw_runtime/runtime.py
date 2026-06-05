from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue


ReleaseGatedDecision = Literal["report", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
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
    "private-key",
    "-----begin",
)
_PROGRAM_ORDER: Final[tuple[str, ...]] = (
    "v0.6.0",
    "v0.7.0",
    "v0.8.0",
    "v0.9.0",
    "v0.10.0",
    "v1.0.0-rc",
)
_STAGE_BY_VERSION: Final[dict[str, str]] = {
    "v0.6.0": "live_spine",
    "v0.7.0": "tool_limbs",
    "v0.8.0": "platform_surface",
    "v0.9.0": "memory_ontology",
    "v0.10.0": "adaptive_zeus",
    "v1.0.0-rc": "live_beta_candidate",
}


class ReleaseGatedUlwStatus(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ReleaseGatedDecision
    target_version: str
    release_stage: Optional[str]
    next_version: Optional[str]
    program_order: tuple[str, ...]
    checkpoint_contract: tuple[str, ...]
    required_checkpoint_evidence: tuple[str, ...]
    blocked_reasons: tuple[str, ...] = ()
    live_spine_contract_available: bool = False
    provider_loopback_contract_available: bool = False
    mcp_loopback_contract_available: bool = False
    provider_loopback_ready: bool = False
    mcp_loopback_ready: bool = False
    approval_lease_required: bool = True
    release_gate_ready: bool = False
    github_release_checkpoint_required: bool = True
    red_green_required: bool = True
    independent_review_required: bool = True
    manual_qa_required: bool = True
    raw_secret_marker_detected: bool = False
    tool_limbs_contract_available: bool = False
    native_tool_catalog_contract_available: bool = False
    mcp_tool_discovery_contract_available: bool = False
    api_connector_contract_available: bool = False
    tool_include_exclude_required: bool = False
    tool_approval_lease_required: bool = False
    tool_security_gate_required: bool = False
    tool_limbs_ready: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> ReleaseGatedUlwStatus:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})


def build_release_gated_ulw_status(
    *,
    target_version: str,
    raw_secret_marker_detected: bool = False,
) -> ReleaseGatedUlwStatus:
    candidate_version = target_version.strip()
    normalized_version = _sanitize_target_version(candidate_version)
    secret_marker_detected = raw_secret_marker_detected or _has_secret_marker(candidate_version)
    stage = _STAGE_BY_VERSION.get(normalized_version)
    blocked_reasons = _blocked_reasons(
        target_version=normalized_version,
        raw_secret_marker_detected=secret_marker_detected,
    )
    live_spine_contract_available = normalized_version == "v0.6.0" and "unknown_target_version" not in blocked_reasons
    tool_limbs_contract_available = normalized_version == "v0.7.0" and "unknown_target_version" not in blocked_reasons
    result = ReleaseGatedUlwStatus(
        decision="blocked" if blocked_reasons else "report",
        target_version=normalized_version,
        release_stage=stage,
        next_version=_next_version(normalized_version),
        program_order=_PROGRAM_ORDER,
        checkpoint_contract=(
            "implementation_complete",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_push_tag_release_complete",
        ),
        required_checkpoint_evidence=(
            "provider_loopback_manual_qa",
            "mcp_loopback_manual_qa",
            "approval_lease_boundary_review",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        ),
        blocked_reasons=blocked_reasons,
        live_spine_contract_available=live_spine_contract_available,
        provider_loopback_contract_available=live_spine_contract_available,
        mcp_loopback_contract_available=live_spine_contract_available,
        provider_loopback_ready=False,
        mcp_loopback_ready=False,
        approval_lease_required=True,
        release_gate_ready=False,
        github_release_checkpoint_required=True,
        red_green_required=True,
        independent_review_required=True,
        manual_qa_required=True,
        raw_secret_marker_detected=secret_marker_detected,
        tool_limbs_contract_available=tool_limbs_contract_available,
        native_tool_catalog_contract_available=tool_limbs_contract_available,
        mcp_tool_discovery_contract_available=tool_limbs_contract_available,
        api_connector_contract_available=tool_limbs_contract_available,
        tool_include_exclude_required=tool_limbs_contract_available,
        tool_approval_lease_required=tool_limbs_contract_available,
        tool_security_gate_required=tool_limbs_contract_available,
        tool_limbs_ready=False,
        credential_material_accessed=False,
        network_opened=False,
        external_delivery_opened=False,
        handler_executed=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _sanitize_target_version(candidate_version: str) -> str:
    if candidate_version in _PROGRAM_ORDER:
        return candidate_version
    return "unknown"


def _blocked_reasons(*, target_version: str, raw_secret_marker_detected: bool) -> tuple[str, ...]:
    reasons = []
    if target_version not in _PROGRAM_ORDER:
        reasons.append("unknown_target_version")
    elif target_version not in {"v0.6.0", "v0.7.0"}:
        reasons.append("prior_release_checkpoint_required")
    if raw_secret_marker_detected:
        reasons.append("raw_secret_marker_detected")
    return tuple(reasons)


def _next_version(target_version: str) -> Optional[str]:
    try:
        index = _PROGRAM_ORDER.index(target_version)
    except ValueError:
        return None
    next_index = index + 1
    if next_index >= len(_PROGRAM_ORDER):
        return None
    return _PROGRAM_ORDER[next_index]


def _has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
