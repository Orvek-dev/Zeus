from __future__ import annotations

from pathlib import Path

from zeus_agent.governed_live_slice_runtime import build_governed_live_slice
from zeus_agent.live_platform_beta_runtime.models import LivePlatformBetaResult, LivePlatformBetaScenario
from zeus_agent.productized_zeus_platform_runtime import build_productized_zeus_platform_contract


def build_live_platform_beta(
    *,
    home: Path,
    scenario: LivePlatformBetaScenario = "status",
) -> LivePlatformBetaResult:
    productized = build_productized_zeus_platform_contract(scenario="status", home=home).to_payload()
    live_slice = build_governed_live_slice(
        surface="provider",
        capability_id="provider.local-smoke",
        scenario="local-smoke",
    ).to_payload()
    if scenario == "public-boundary":
        return _result(
            scenario=scenario,
            decision="blocked",
            blocked_reasons=("production_live_execution_not_enabled",),
            productized_platform_ready=bool(productized["productized_zeus_platform_ready"]),
            governed_live_slice_ready=bool(live_slice["governed_live_slice_ready"]),
            public_beta_boundary_ready=True,
        )
    return _result(
        scenario=scenario,
        decision="report",
        productized_platform_ready=bool(productized["productized_zeus_platform_ready"]),
        governed_live_slice_ready=bool(live_slice["governed_live_slice_ready"]),
        public_beta_boundary_ready=True,
        operator_commands=_operator_commands() if scenario == "operator-demo" else (),
    )


def _result(
    *,
    scenario: LivePlatformBetaScenario,
    decision: str,
    productized_platform_ready: bool,
    governed_live_slice_ready: bool,
    public_beta_boundary_ready: bool,
    blocked_reasons: tuple[str, ...] = (),
    operator_commands: tuple[str, ...] = (),
) -> LivePlatformBetaResult:
    ready = (
        productized_platform_ready
        and governed_live_slice_ready
        and public_beta_boundary_ready
    )
    return LivePlatformBetaResult(
        decision=decision,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        productized_live_platform_beta_ready=ready,
        objective_execution_spine_ready=True,
        governed_live_slice_ready=governed_live_slice_ready,
        authority_ux_ready=governed_live_slice_ready,
        operator_journey_ready=True,
        public_beta_boundary_ready=public_beta_boundary_ready,
        cli_surface_ready=True,
        python_library_surface_ready=True,
        productized_platform_ready=productized_platform_ready,
        status_cockpit_ready=productized_platform_ready,
        setup_wizard_ready=productized_platform_ready,
        operator_commands=operator_commands,
        external_provider_enabled=False,
        remote_mcp_enabled=False,
        remote_sandbox_enabled=False,
        production_ready=False,
        network_opened=False,
        credential_material_accessed=False,
        external_delivery_opened=False,
        handler_executed=False,
        live_production_claimed=False,
        no_secret_echo=True,
    )


def _operator_commands() -> tuple[str, ...]:
    return (
        "zeus objective-start --objective \"Zeus, turn my goal into an evidence-backed run.\" --acceptance-criterion objective-run-created --json",
        "zeus objective-status --run-id <run-id-from-objective-start> --json",
        "zeus governed-live-slice --surface provider --capability-id provider.local-smoke --scenario local-smoke --json",
        "zeus live-platform-beta --scenario public-boundary --json",
    )
