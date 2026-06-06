from __future__ import annotations

from pathlib import Path
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.cognitive_provider_activation_runtime import build_cognitive_provider_activation_contract
from zeus_agent.productized_zeus_platform_runtime.models import ProductizedZeusPlatformContract
from zeus_agent.productized_zeus_platform_runtime.models import ProductizedZeusPlatformDecision
from zeus_agent.productized_zeus_platform_runtime.models import ProductizedZeusPlatformScenario
from zeus_agent.productized_zeus_platform_runtime.models import ProductizedZeusPayloads
from zeus_agent.production_scale_platform_runtime import build_production_scale_platform_contract
from zeus_agent.real_product_platform_runtime import build_real_product_platform_contract
from zeus_agent.security.credentials import contains_secret_material
from zeus_agent.setup_runtime import setup_plan

_OPERATOR_COMMANDS: Final[tuple[str, ...]] = (
    "zeus productized-platform --scenario zeus-persona --json",
    "zeus productized-platform --scenario setup-status --json",
    "zeus productized-platform --scenario cockpit --json",
    "zeus productized-platform --scenario plugin-tenant-learning --json",
    "zeus cognitive-provider-activation --scenario fake-provider-intent --json",
    "zeus release-gated-ulw --target-version v4.0.0 --json",
)


def build_productized_zeus_platform_contract(
    *,
    scenario: str = "status",
    home: Optional[Path] = None,
    operator_note: Optional[str] = None,
) -> ProductizedZeusPlatformContract:
    if operator_note is not None and contains_secret_material(operator_note):
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("raw_secret_marker_detected",),
            raw_secret_marker_detected=True,
        )
    parsed = _parse_scenario(scenario)
    if parsed is None:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_productized_zeus_platform_scenario",),
        )
    return _build(parsed, home=home)


def _build(
    scenario: ProductizedZeusPlatformScenario,
    *,
    home: Optional[Path],
) -> ProductizedZeusPlatformContract:
    if scenario == "public-boundary":
        return _public_boundary(home=home)
    payloads = _payloads(home=home)
    if scenario == "zeus-persona":
        return _persona(payloads)
    if scenario == "setup-status":
        return _setup_status(payloads)
    if scenario == "cockpit":
        return _cockpit(payloads)
    if scenario == "operator-map":
        return _operator_map()
    if scenario == "plugin-tenant-learning":
        return _plugin_tenant_learning(payloads)
    return _status(payloads)


def _status(payloads: ProductizedZeusPayloads) -> ProductizedZeusPlatformContract:
    ready = _all_ready(payloads)
    return _contract(
        decision="report" if ready else "blocked",
        scenario="status",
        blocked_reasons=() if ready else ("productized_surface_not_ready",),
        productized_zeus_platform_ready=ready,
        installable_user_journey_ready=ready,
        **payloads.to_contract_parts(),
    )


def _persona(payloads: ProductizedZeusPayloads) -> ProductizedZeusPlatformContract:
    ready = payloads.product.get("zeus_korean_call_response") == "네, 제우스입니다."
    return _contract(
        decision="report" if ready else "blocked",
        scenario="zeus-persona",
        blocked_reasons=() if ready else ("zeus_persona_unavailable",),
        zeus_persona_ready=ready,
        **payloads.to_contract_parts(),
    )


def _setup_status(payloads: ProductizedZeusPayloads) -> ProductizedZeusPlatformContract:
    ready = bool(payloads.setup.get("setup_plan_created")) and not bool(payloads.setup.get("raw_secret_echoed"))
    return _contract(
        decision="report" if ready else "blocked",
        scenario="setup-status",
        blocked_reasons=() if ready else ("setup_plan_unavailable",),
        setup_wizard_ready=ready,
        **payloads.to_contract_parts(),
    )


def _cockpit(payloads: ProductizedZeusPayloads) -> ProductizedZeusPlatformContract:
    ready = bool(payloads.product.get("product_platform_ready"))
    return _contract(
        decision="report" if ready else "blocked",
        scenario="cockpit",
        blocked_reasons=() if ready else ("product_cockpit_unavailable",),
        status_cockpit_ready=ready,
        **payloads.to_contract_parts(),
    )


def _operator_map() -> ProductizedZeusPlatformContract:
    return _contract(
        decision="report",
        scenario="operator-map",
        operator_command_map_ready=True,
    )


def _plugin_tenant_learning(payloads: ProductizedZeusPayloads) -> ProductizedZeusPlatformContract:
    ready = _scale_ready(payloads.scale)
    return _contract(
        decision="report" if ready else "blocked",
        scenario="plugin-tenant-learning",
        blocked_reasons=() if ready else ("scale_contract_unavailable",),
        **payloads.to_contract_parts(),
    )


def _public_boundary(*, home: Optional[Path]) -> ProductizedZeusPlatformContract:
    payloads = _payloads(home=home)
    return _contract(
        decision="blocked",
        scenario="public-boundary",
        blocked_reasons=("production_live_execution_not_enabled",),
        public_boundary_ready=True,
        **payloads.to_contract_parts(),
    )


def _contract(
    *,
    decision: ProductizedZeusPlatformDecision,
    scenario: ProductizedZeusPlatformScenario,
    blocked_reasons: tuple[str, ...] = (),
    productized_zeus_platform_ready: bool = False,
    zeus_persona_ready: bool = False,
    setup_wizard_ready: bool = False,
    status_cockpit_ready: bool = False,
    operator_command_map_ready: bool = False,
    public_boundary_ready: bool = False,
    installable_user_journey_ready: bool = False,
    raw_secret_marker_detected: bool = False,
    **parts: dict[str, JsonValue],
) -> ProductizedZeusPlatformContract:
    cognitive = _dict_part(parts, "cognitive_contract")
    product = _dict_part(parts, "product_platform_contract")
    scale = _dict_part(parts, "production_scale_contract")
    setup = _dict_part(parts, "setup_plan")
    result = ProductizedZeusPlatformContract(
        decision=decision,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        productized_zeus_platform_ready=productized_zeus_platform_ready,
        zeus_persona_ready=zeus_persona_ready or product.get("zeus_korean_call_response") == "네, 제우스입니다.",
        setup_wizard_ready=setup_wizard_ready or bool(setup.get("setup_plan_created")),
        status_cockpit_ready=status_cockpit_ready or bool(product.get("product_platform_ready")),
        operator_command_map_ready=operator_command_map_ready,
        cognitive_provider_activation_ready=bool(cognitive.get("cognitive_provider_activation_ready")),
        plugin_ecosystem_ready=bool(scale.get("plugin_ecosystem_available")),
        tenant_auth_ready=bool(scale.get("tenant_model_available")) and bool(
            scale.get("role_scope_enforcement_available")
        ),
        candidate_learning_ready=bool(scale.get("candidate_only_learning_available")),
        public_boundary_ready=public_boundary_ready,
        installable_user_journey_ready=installable_user_journey_ready,
        setup_plan=setup or None,
        cognitive_contract=cognitive or None,
        product_platform_contract=product or None,
        production_scale_contract=scale or None,
        operator_commands=_OPERATOR_COMMANDS,
        operator_command_count=len(_OPERATOR_COMMANDS),
        network_opened=_any_flag(cognitive, product, scale, "network_opened"),
        handler_executed=_any_flag(cognitive, product, scale, "handler_executed"),
        credential_material_accessed=_any_flag(cognitive, product, scale, "credential_material_accessed"),
        external_delivery_opened=_any_flag(cognitive, product, scale, "external_delivery_opened"),
        authority_widened=_any_flag(cognitive, product, scale, "authority_widened"),
        active_rule_written=_any_flag(cognitive, product, scale, "active_rule_written"),
        live_production_claimed=_any_flag(cognitive, product, scale, "live_production_claimed"),
        settings_written=bool(setup.get("settings_written", False)),
        raw_secret_marker_detected=raw_secret_marker_detected,
    )
    return result.with_secret_scan()


def _payloads(*, home: Optional[Path]) -> ProductizedZeusPayloads:
    safe_home = home or Path.cwd()
    return ProductizedZeusPayloads(
        setup=setup_plan(home=safe_home, provider_id="fake", local=True),
        cognitive=build_cognitive_provider_activation_contract(scenario="fake-provider-intent").to_payload(),
        product=build_real_product_platform_contract(scenario="status", home=safe_home).to_payload(),
        scale=build_production_scale_platform_contract(scenario="status", home=safe_home).to_payload(),
    )


def _all_ready(payloads: ProductizedZeusPayloads) -> bool:
    return bool(payloads.cognitive.get("cognitive_provider_activation_ready")) and bool(
        payloads.product.get("product_platform_ready")
    ) and _scale_ready(payloads.scale) and bool(payloads.setup.get("setup_plan_created"))


def _scale_ready(scale: dict[str, JsonValue]) -> bool:
    return bool(scale.get("production_scale_platform_ready")) and bool(scale.get("tenant_model_available"))


def _parse_scenario(value: str) -> Optional[ProductizedZeusPlatformScenario]:
    stripped = value.strip()
    scenarios: tuple[ProductizedZeusPlatformScenario, ...] = (
        "status",
        "zeus-persona",
        "setup-status",
        "cockpit",
        "operator-map",
        "plugin-tenant-learning",
        "public-boundary",
    )
    return stripped if stripped in scenarios else None


def _dict_part(parts: dict[str, JsonValue], key: str) -> dict[str, JsonValue]:
    value = parts.get(key, {})
    return value if isinstance(value, dict) else {}


def _any_flag(
    first: dict[str, JsonValue],
    second: dict[str, JsonValue],
    third: dict[str, JsonValue],
    key: str,
) -> bool:
    return bool(first.get(key, False) or second.get(key, False) or third.get(key, False))
