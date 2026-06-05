from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

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
    "token=sk",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


class PlatformCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report", "blocked"]
    surface_count: int
    selected_surface: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    api_server_started: bool = False
    acp_session_opened: bool = False
    batch_executed: bool = False
    cli_process_started: bool = False
    python_library_handler_executed: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class PlatformCockpitRuntime:
    def build(self, *, surface_id: Optional[str] = None) -> PlatformCockpitResult:
        surfaces = _surface_summaries()
        selected = _find_selected_surface(surfaces, surface_id)
        blocked_reasons = _blocked_reasons(surface_id=surface_id, selected_surface=selected)
        result = PlatformCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            surface_count=len(surfaces),
            selected_surface=selected,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(surface_id=surface_id),
            api_server_started=False,
            acp_session_opened=False,
            batch_executed=False,
            cli_process_started=False,
            python_library_handler_executed=False,
            credential_material_accessed=False,
            network_opened=False,
            handler_executed=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _surface_summaries() -> tuple[dict[str, JsonValue], ...]:
    return (
        {
            "surface_id": "cli",
            "display_name": "CLI",
            "kind": "interactive",
            "commands": ["zeus-chat", "live", "platform", "tools", "runtime", "workflow"],
            "execution_policy": "operator_invoked",
            "handler_executed": False,
            "network_opened": False,
            "live_production_claimed": False,
        },
        {
            "surface_id": "api",
            "display_name": "API Server",
            "kind": "http",
            "routes": ["/health", "/v1/health", "/v1/capabilities", "/v1/models", "/v1/chat/completions", "/v1/responses", "/v1/runs"],
            "loopback_default": True,
            "non_loopback_requires_review": True,
            "server_started": False,
            "handler_executed": False,
            "network_opened": False,
            "live_production_claimed": False,
        },
        {
            "surface_id": "acp",
            "display_name": "Agent Client Protocol",
            "kind": "jsonrpc",
            "allowed_methods": ["initialize", "zeus.objective.compile"],
            "unknown_method_policy": "blocked",
            "session_opened": False,
            "handler_executed": False,
            "network_opened": False,
            "live_production_claimed": False,
        },
        {
            "surface_id": "batch",
            "display_name": "Batch Runner",
            "kind": "batch",
            "objective_execution": "compile_only",
            "items_execute_handlers": False,
            "batch_executed": False,
            "network_opened": False,
            "live_production_claimed": False,
        },
        {
            "surface_id": "python-library",
            "display_name": "Python Library",
            "kind": "library",
            "facades": ["chat", "compile_objective", "live_status", "tool_status", "runtime_status", "workflow_status"],
            "handler_executed": False,
            "network_opened": False,
            "live_production_claimed": False,
        },
    )


def _find_selected_surface(
    surfaces: tuple[dict[str, JsonValue], ...],
    surface_id: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if surface_id is None:
        return None
    for surface in surfaces:
        if surface["surface_id"] == surface_id:
            return surface
    return None


def _blocked_reasons(
    *,
    surface_id: Optional[str],
    selected_surface: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if surface_id is not None and selected_surface is None:
        return ("unknown_platform_surface",)
    return ()


def _recommended_next_commands(*, surface_id: Optional[str]) -> tuple[str, ...]:
    if surface_id is None:
        return (
            "zeus platform --surface api --json",
            "zeus platform --surface acp --json",
            "zeus live --json",
        )
    return (
        "zeus live --json",
        "zeus gateway --json",
        "zeus security --json",
    )


def _no_secret_echo(result: PlatformCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
