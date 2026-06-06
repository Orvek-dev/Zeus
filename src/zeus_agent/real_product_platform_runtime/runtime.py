from __future__ import annotations

from pathlib import Path
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.mcp_cockpit_runtime import McpCockpitRuntime
from zeus_agent.model_cockpit_runtime import ModelCockpitRuntime
from zeus_agent.persona_cockpit_runtime import PersonaCockpitRuntime
from zeus_agent.platform_cockpit_runtime import PlatformCockpitRuntime
from zeus_agent.real_product_platform_runtime.factory import build_contract
from zeus_agent.real_product_platform_runtime.models import RealProductPlatformContract
from zeus_agent.real_product_platform_runtime.models import RealProductPlatformScenario
from zeus_agent.runtime_cockpit import RuntimeCockpitRuntime

_SUPPORTED_SCENARIOS: Final[frozenset[str]] = frozenset(
    {
        "status",
        "persona-smoke",
        "platform-cockpit-smoke",
        "live-status-smoke",
        "operator-command-map",
        "public-boundary",
    },
)
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
_OPERATOR_COMMANDS: Final[tuple[str, ...]] = (
    "zeus persona --profile work --json",
    "zeus platform --surface api --json",
    "zeus live --json",
    "zeus model --provider-id openai --json",
    "zeus mcp --server-id mcp.github --json",
    "zeus runtime --backend terminal --json",
    "zeus product-platform-runtime --scenario live-status-smoke --json",
)


def build_real_product_platform_contract(
    *,
    scenario: str = "status",
    home: Optional[Path] = None,
    operator_note: Optional[str] = None,
) -> RealProductPlatformContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in _SUPPORTED_SCENARIOS:
        return build_contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_real_product_platform_scenario",),
        )
    parsed_scenario = _parse_scenario(safe_scenario)
    if operator_note is not None and _has_secret_marker(operator_note):
        return build_contract(
            decision="blocked",
            scenario=parsed_scenario,
            blocked_reasons=("raw_secret_marker_detected",),
            raw_secret_marker_detected=True,
        )
    return _build(parsed_scenario, home=home)


def _build(
    scenario: RealProductPlatformScenario,
    *,
    home: Optional[Path],
) -> RealProductPlatformContract:
    if scenario == "status":
        return _status(home=home)
    if scenario == "persona-smoke":
        return _persona_smoke(home=home)
    if scenario == "platform-cockpit-smoke":
        return _platform_cockpit_smoke(home=home)
    if scenario == "live-status-smoke":
        return _live_status_smoke(home=home)
    if scenario == "operator-command-map":
        return _operator_command_map()
    return _public_boundary(home=home)


def _status(*, home: Optional[Path]) -> RealProductPlatformContract:
    contracts = _surface_contracts(home=home)
    blocked_count = _blocked_surface_count(contracts)
    return build_contract(
        decision="report" if blocked_count == 0 else "blocked",
        scenario="status",
        blocked_reasons=() if blocked_count == 0 else ("blocked_status_surface_detected",),
        **contracts,
        status_surface_count=len(contracts),
        blocked_surface_count=blocked_count,
        operator_commands=_OPERATOR_COMMANDS,
        product_platform_ready=blocked_count == 0,
    )


def _persona_smoke(*, home: Optional[Path]) -> RealProductPlatformContract:
    contract = PersonaCockpitRuntime(home or Path.cwd()).build(profile="work").to_payload()
    ready = contract["decision"] == "report" and _selected_profile(contract) == "work"
    return build_contract(
        decision="report" if ready else "blocked",
        scenario="persona-smoke",
        blocked_reasons=() if ready else ("persona_work_profile_unavailable",),
        persona_contract=contract,
        status_surface_count=1,
        operator_commands=_OPERATOR_COMMANDS,
        product_platform_ready=ready,
        persona_surface_ready=ready,
    )


def _platform_cockpit_smoke(*, home: Optional[Path]) -> RealProductPlatformContract:
    contract = PlatformCockpitRuntime().build(surface_id="api").to_payload()
    ready = contract["decision"] == "report" and _selected_surface(contract) == "api"
    return build_contract(
        decision="report" if ready else "blocked",
        scenario="platform-cockpit-smoke",
        blocked_reasons=() if ready else ("platform_api_surface_unavailable",),
        platform_contract=contract,
        status_surface_count=1,
        operator_commands=_OPERATOR_COMMANDS,
        product_platform_ready=ready,
        platform_status_ready=ready,
    )


def _live_status_smoke(*, home: Optional[Path]) -> RealProductPlatformContract:
    contract = LiveCockpitRuntime(home=home).build(include_smoke=False).to_payload()
    ready = contract["decision"] == "report" and contract["approval_required"] is True
    return build_contract(
        decision="report" if ready else "blocked",
        scenario="live-status-smoke",
        blocked_reasons=() if ready else ("live_status_surface_unavailable",),
        live_cockpit_contract=contract,
        status_surface_count=1,
        operator_commands=_OPERATOR_COMMANDS,
        product_platform_ready=ready,
        live_status_ready=ready,
    )


def _operator_command_map() -> RealProductPlatformContract:
    return build_contract(
        decision="report",
        scenario="operator-command-map",
        status_surface_count=0,
        operator_commands=_OPERATOR_COMMANDS,
        product_platform_ready=True,
        operator_command_map_ready=True,
    )


def _public_boundary(*, home: Optional[Path]) -> RealProductPlatformContract:
    contracts = _surface_contracts(home=home)
    return build_contract(
        decision="blocked",
        scenario="public-boundary",
        blocked_reasons=("production_live_execution_not_enabled",),
        **contracts,
        status_surface_count=len(contracts),
        blocked_surface_count=_blocked_surface_count(contracts),
        operator_commands=_OPERATOR_COMMANDS,
        public_boundary_ready=True,
    )


def _surface_contracts(*, home: Optional[Path]) -> dict[str, dict[str, JsonValue]]:
    return {
        "persona_contract": PersonaCockpitRuntime(home or Path.cwd()).build().to_payload(),
        "platform_contract": PlatformCockpitRuntime().build().to_payload(),
        "live_cockpit_contract": LiveCockpitRuntime(home=home).build(include_smoke=False).to_payload(),
        "model_cockpit_contract": ModelCockpitRuntime().build().to_payload(),
        "mcp_cockpit_contract": McpCockpitRuntime().build().to_payload(),
        "runtime_cockpit_contract": RuntimeCockpitRuntime().build(root=home).to_payload(),
    }


def _blocked_surface_count(contracts: dict[str, dict[str, JsonValue]]) -> int:
    return sum(1 for contract in contracts.values() if contract["decision"] == "blocked")


def _selected_profile(contract: dict[str, JsonValue]) -> str:
    selected = contract["selected_profile"]
    if not isinstance(selected, dict):
        return ""
    return str(selected.get("profile", ""))


def _selected_surface(contract: dict[str, JsonValue]) -> str:
    selected = contract["selected_surface"]
    if not isinstance(selected, dict):
        return ""
    return str(selected.get("surface_id", ""))


def _parse_scenario(value: str) -> RealProductPlatformScenario:
    if value == "status":
        return "status"
    if value == "persona-smoke":
        return "persona-smoke"
    if value == "platform-cockpit-smoke":
        return "platform-cockpit-smoke"
    if value == "live-status-smoke":
        return "live-status-smoke"
    if value == "operator-command-map":
        return "operator-command-map"
    if value == "public-boundary":
        return "public-boundary"
    return "status"


def _has_secret_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
