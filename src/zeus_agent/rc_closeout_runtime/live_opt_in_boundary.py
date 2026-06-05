from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue


BoundaryDecision = Literal["report", "blocked"]
RequestedMode = Literal["migration_guide", "production_live"]

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
    "-----begin",
)


class RcLiveSurfaceBoundary(BaseModel):
    model_config = _MODEL_CONFIG

    surface_id: str
    hermes_surface: str
    zeus_surface: str
    rc_state: Literal["local_ready_live_opt_in_required"]
    opt_in_steps: tuple[str, ...]


class RcLiveOptInBoundaryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: BoundaryDecision
    requested_mode: RequestedMode
    hermes_entrypoints: tuple[str, ...]
    hermes_entrypoint_count: int
    surfaces: tuple[RcLiveSurfaceBoundary, ...]
    surface_ids: tuple[str, ...]
    surface_count: int
    blocked_reasons: tuple[str, ...]
    explicit_live_opt_in_required: bool = True
    project_mode_release_required: bool = True
    production_live_ready: bool = False
    migration_guide_path: str = "docs/zeus-hermes-live-opt-in-boundary.md"
    raw_request_redacted: bool = True
    credential_material_accessed: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RcLiveOptInBoundaryResult:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})


def build_rc_live_opt_in_boundary(
    *,
    requested_mode: RequestedMode = "migration_guide",
    raw_request: Optional[str] = None,
) -> RcLiveOptInBoundaryResult:
    surfaces = _surface_boundaries()
    blocked_reasons = _blocked_reasons(requested_mode)
    decision: BoundaryDecision = "blocked" if blocked_reasons else "report"
    result = RcLiveOptInBoundaryResult(
        decision=decision,
        requested_mode=requested_mode,
        hermes_entrypoints=_hermes_entrypoints(),
        hermes_entrypoint_count=len(_hermes_entrypoints()),
        surfaces=surfaces,
        surface_ids=tuple(surface.surface_id for surface in surfaces),
        surface_count=len(surfaces),
        blocked_reasons=blocked_reasons,
        explicit_live_opt_in_required=True,
        project_mode_release_required=True,
        production_live_ready=False,
        raw_request_redacted=raw_request is not None,
        credential_material_accessed=False,
        network_opened=False,
        external_delivery_opened=False,
        handler_executed=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _blocked_reasons(requested_mode: RequestedMode) -> tuple[str, ...]:
    if requested_mode == "production_live":
        return (
            "separate_project_mode_release_required",
            "production_live_claim_blocked",
            "live_surface_evidence_required",
        )
    return ()


def _hermes_entrypoints() -> tuple[str, ...]:
    return (
        "cli",
        "gateway",
        "acp",
        "batch_runner",
        "api_server",
        "python_library",
        "mcp",
        "tools",
        "memory",
        "skills",
    )


def _surface_boundaries() -> tuple[RcLiveSurfaceBoundary, ...]:
    return (
        _surface("provider_api", "provider resolution", "model_runtime"),
        _surface("mcp_tools", "MCP tool dispatch", "mcp_runtime"),
        _surface("gateway_delivery", "messaging gateway", "gateway_runtime"),
        _surface("browser_web", "browser and web backends", "browser_runtime/web_runtime"),
        _surface("terminal_sandbox", "terminal and sandbox backend", "terminal_runtime/sandbox_runtime"),
        _surface("cron_batch", "cron and batch runner", "workflow_runtime/batch_runtime"),
        _surface("plugin_supply_chain", "plugins and toolsets", "plugin_runtime/tool_runtime"),
        _surface("memory_ontology", "memory and skills", "memory_graph_runtime/wiki_runtime"),
        _surface("api_acp", "API server and ACP", "api_runtime/acp_runtime"),
    )


def _surface(surface_id: str, hermes_surface: str, zeus_surface: str) -> RcLiveSurfaceBoundary:
    return RcLiveSurfaceBoundary(
        surface_id=surface_id,
        hermes_surface=hermes_surface,
        zeus_surface=zeus_surface,
        rc_state="local_ready_live_opt_in_required",
        opt_in_steps=(
            "bind objective contract and authority lease",
            "resolve scoped credentials without raw material echo",
            "run preflight and explicit human approval",
            "record cleanup, trace, and rollback evidence",
            "pass separate project-mode release gate before production claim",
        ),
    )
