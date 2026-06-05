from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.platform_cockpit_runtime import PlatformCockpitRuntime

PlatformSurfaceDecision = Literal["report", "blocked"]

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
_TARGET_VERSION: Final = "v0.8.0"


class PlatformSurfaceContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: PlatformSurfaceDecision
    target_version: str
    objective_contract_id: str
    selected_surface_id: Optional[str] = None
    selected_surface: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    surface_count: int
    cli_surface_contract_available: bool = True
    api_server_contract_available: bool = True
    gateway_surface_contract_available: bool = True
    acp_adapter_contract_available: bool = True
    batch_runner_contract_available: bool = True
    python_library_contract_available: bool = True
    loopback_default_required: bool = True
    non_loopback_review_required: bool = True
    approval_lease_required: bool = True
    security_gate_required: bool = True
    evidence_capture_required: bool = True
    platform_surface_ready: bool = False
    live_external_execution_enabled: bool = False
    raw_secret_marker_detected: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> PlatformSurfaceContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        return self.model_copy(
            update={"no_secret_echo": not any(marker in serialized for marker in _SECRET_MARKERS)},
        )


def build_platform_surface_contract(*, surface_id: Optional[str] = None) -> PlatformSurfaceContract:
    candidate_surface_id = None if surface_id is None else surface_id.strip()
    raw_secret_marker_detected = _has_secret_marker(candidate_surface_id or "")
    cockpit = PlatformCockpitRuntime().build(surface_id=candidate_surface_id)
    selected_surface = cockpit.selected_surface
    selected_surface_id = _safe_selected_surface_id(candidate_surface_id, selected_surface)
    blocked_reasons = _blocked_reasons(
        cockpit_blocked_reasons=cockpit.blocked_reasons,
        raw_secret_marker_detected=raw_secret_marker_detected,
    )
    result = PlatformSurfaceContract(
        decision="blocked" if blocked_reasons else "report",
        target_version=_TARGET_VERSION,
        objective_contract_id="zeus.v0.8.0.platform_surface",
        selected_surface_id=selected_surface_id,
        selected_surface=selected_surface,
        blocked_reasons=blocked_reasons,
        surface_count=cockpit.surface_count,
        raw_secret_marker_detected=raw_secret_marker_detected,
        credential_material_accessed=cockpit.credential_material_accessed,
        network_opened=cockpit.network_opened,
        handler_executed=cockpit.handler_executed,
        external_delivery_opened=cockpit.external_delivery_opened,
        live_production_claimed=cockpit.live_production_claimed,
    )
    return result.with_secret_scan()


def _safe_selected_surface_id(
    candidate_surface_id: Optional[str],
    selected_surface: Optional[dict[str, JsonValue]],
) -> Optional[str]:
    if candidate_surface_id is None:
        return None
    if selected_surface is not None:
        surface_id = selected_surface.get("surface_id")
        return surface_id if isinstance(surface_id, str) else "unknown"
    return "unknown"


def _blocked_reasons(
    *,
    cockpit_blocked_reasons: tuple[str, ...],
    raw_secret_marker_detected: bool,
) -> tuple[str, ...]:
    reasons = list(cockpit_blocked_reasons)
    if raw_secret_marker_detected:
        reasons.append("raw_secret_marker_detected")
    return tuple(reasons)


def _has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
