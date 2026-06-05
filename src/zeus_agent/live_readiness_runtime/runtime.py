from __future__ import annotations

import json
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationInfo, field_validator

from zeus_agent.live_beta_runtime import LiveBetaActivationResult
from zeus_agent.mcp_runtime import McpDiscoverySnapshot
from zeus_agent.security.credentials import redact_secret_spans

ReadinessState = Literal["planned_wave", "dry_run", "live_beta", "blocked"]
ReadinessSurfaceKind = Literal[
    "provider",
    "mcp",
    "gateway",
    "api",
    "browser",
    "terminal",
    "sandbox",
    "cron",
    "plugin",
    "memory",
]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return redact_secret_spans(normalized)


class ReadinessSurface(BaseModel):
    model_config = _MODEL_CONFIG

    surface_id: str
    surface_kind: ReadinessSurfaceKind
    state: ReadinessState
    production_ready: bool = False
    missing_requirements: tuple[str, ...] = ()
    risk_notes: tuple[str, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False

    @field_validator("surface_id")
    @classmethod
    def _validate_surface_id(cls, value: str) -> str:
        return _require_non_empty(value, "surface_id")

    @field_validator("missing_requirements", "risk_notes")
    @classmethod
    def _validate_text_tuple(cls, values: tuple[str, ...], info: ValidationInfo) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, info.field_name) for value in values)


class LiveReadinessReport(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report"]
    surfaces: tuple[ReadinessSurface, ...]
    extra_notes: tuple[str, ...] = ()
    surface_count: int = Field(ge=0)
    live_beta_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    user_approval_required: bool
    recommended_next_actions: tuple[str, ...]
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    @field_validator("extra_notes", "recommended_next_actions")
    @classmethod
    def _validate_text_tuple(cls, values: tuple[str, ...], info: ValidationInfo) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, info.field_name) for value in values)

    def surface_by_id(self, surface_id: str) -> ReadinessSurface:
        safe_id = _require_non_empty(surface_id, "surface_id")
        for surface in self.surfaces:
            if surface.surface_id == safe_id:
                return surface
        raise ValueError("unknown_readiness_surface")

    def to_payload(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "surface_count": self.surface_count,
            "live_beta_count": self.live_beta_count,
            "blocked_count": self.blocked_count,
            "user_approval_required": self.user_approval_required,
            "recommended_next_actions": self.recommended_next_actions,
            "surfaces": [surface.model_dump(mode="json") for surface in self.surfaces],
            "extra_notes": self.extra_notes,
            "network_opened": self.network_opened,
            "handler_executed": self.handler_executed,
            "external_delivery_opened": self.external_delivery_opened,
            "credential_material_accessed": self.credential_material_accessed,
            "no_secret_echo": self.no_secret_echo,
            "live_production_claimed": self.live_production_claimed,
        }


class LiveReadinessRuntime:
    def build_report(
        self,
        *,
        beta_activations: tuple[LiveBetaActivationResult, ...] = (),
        mcp_discoveries: tuple[McpDiscoverySnapshot, ...] = (),
        extra_notes: tuple[str, ...] = (),
    ) -> LiveReadinessReport:
        surfaces = {surface.surface_id: surface for surface in _default_surfaces()}
        for activation in beta_activations:
            surfaces[activation.surface_id] = _surface_from_activation(activation)
        for discovery in mcp_discoveries:
            surfaces[discovery.server_id] = _surface_from_discovery(discovery)
        ordered = tuple(surfaces[key] for key in sorted(surfaces))
        report = LiveReadinessReport(
            decision="report",
            surfaces=ordered,
            extra_notes=tuple(redact_secret_spans(note) for note in extra_notes),
            surface_count=len(ordered),
            live_beta_count=sum(1 for surface in ordered if surface.state == "live_beta"),
            blocked_count=sum(1 for surface in ordered if surface.state == "blocked"),
            user_approval_required=any("approval_required" in surface.missing_requirements for surface in ordered),
            recommended_next_actions=_recommended_next_actions(ordered),
        )
        return report.model_copy(update={"no_secret_echo": _no_secret_echo(report)})


def _default_surfaces() -> tuple[ReadinessSurface, ...]:
    return (
        ReadinessSurface(surface_id="provider.external.openai", surface_kind="provider", state="blocked", missing_requirements=("approval_required", "live_lease_required", "probe_required")),
        ReadinessSurface(surface_id="mcp.catalog", surface_kind="mcp", state="dry_run", risk_notes=("resources_prompts_disabled", "discovery_parser_available")),
        ReadinessSurface(surface_id="gateway.adapters", surface_kind="gateway", state="blocked", missing_requirements=("approval_required", "gateway_allowlist_required", "pairing_required")),
        ReadinessSurface(surface_id="api.local", surface_kind="api", state="dry_run", risk_notes=("loopback_only",)),
        ReadinessSurface(surface_id="browser.dispatch", surface_kind="browser", state="dry_run", missing_requirements=("approval_required", "evidence_required")),
        ReadinessSurface(surface_id="terminal.dispatch", surface_kind="terminal", state="dry_run", risk_notes=("sandbox_policy_required",)),
        ReadinessSurface(surface_id="sandbox.dispatch", surface_kind="sandbox", state="dry_run", missing_requirements=("cleanup_required", "egress_denied")),
        ReadinessSurface(surface_id="cron.standing_order", surface_kind="cron", state="blocked", missing_requirements=("approval_required", "headless_guard_required")),
        ReadinessSurface(surface_id="plugin.runtime", surface_kind="plugin", state="dry_run", risk_notes=("quarantined_by_default",)),
        ReadinessSurface(surface_id="memory.graph", surface_kind="memory", state="dry_run", risk_notes=("local_first", "provenance_required")),
    )


def _surface_from_activation(activation: LiveBetaActivationResult) -> ReadinessSurface:
    return ReadinessSurface(
        surface_id=activation.surface_id,
        surface_kind=activation.surface_kind,
        state="live_beta" if activation.decision == "live_beta" else "blocked",
        production_ready=False,
        missing_requirements=activation.reasons,
        risk_notes=("beta_only", "production_ready_false"),
        metadata={
            "lease_authorized": activation.lease_authorized,
            "approval_receipt_bound": activation.approval_receipt_bound,
            "capability_id": activation.capability_id,
            "evidence_target": activation.evidence_target,
        },
        network_opened=activation.network_opened,
        handler_executed=activation.handler_executed,
        external_delivery_opened=activation.external_delivery_opened,
    )


def _surface_from_discovery(discovery: McpDiscoverySnapshot) -> ReadinessSurface:
    trusted = any(tool.trusted_annotations_applied for tool in discovery.tools)
    return ReadinessSurface(
        surface_id=discovery.server_id,
        surface_kind="mcp",
        state="dry_run",
        production_ready=False,
        risk_notes=("discovery_only", "annotations_metadata_only"),
        metadata={
            "tool_count": discovery.tool_count,
            "list_changed": discovery.list_changed,
            "trusted_annotations_applied": trusted,
            "unsafe_marker_count": discovery.unsafe_marker_count,
        },
        network_opened=discovery.network_opened,
        handler_executed=discovery.handler_executed,
    )


def _recommended_next_actions(surfaces: tuple[ReadinessSurface, ...]) -> tuple[str, ...]:
    actions: list[str] = []
    for surface in surfaces:
        for requirement in surface.missing_requirements:
            if requirement not in actions:
                actions.append(requirement)
    if "approval_required" in actions:
        actions.append("human_in_the_loop_review")
    return tuple(actions)


def _no_secret_echo(report: LiveReadinessReport) -> bool:
    serialized = json.dumps(report.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
