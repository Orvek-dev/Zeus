from __future__ import annotations

from pathlib import Path

from zeus_agent.governed_live_connector_platform_runtime import build_governed_live_connector_platform
from zeus_agent.higher_order_agent_os_runtime.models import (
    HigherOrderAgentOsResult,
    HigherOrderAgentOsScenario,
)
from zeus_agent.objective_compiler_ux_runtime import build_objective_compiler_workflow


def build_higher_order_agent_os(
    *,
    home: Path,
    scenario: HigherOrderAgentOsScenario = "status",
) -> HigherOrderAgentOsResult:
    objective = build_objective_compiler_workflow(
        home=home,
        objective="Zeus, compile an operator goal into a governed workflow.",
        session_id="session.v600.agent-os",
        principal_id="operator.local",
        task_count=4,
        requires_code=True,
        requires_research=True,
        risk_level="normal",
    )
    connectors = build_governed_live_connector_platform(
        home=home,
        scenario="trusted-local-smoke",
    )
    blocked_reasons = _blocked_reasons(scenario)
    ready = (
        objective.objective_compiler_workflow_ready
        and connectors.connectors_ready
        and not blocked_reasons
    )
    return HigherOrderAgentOsResult(
        decision="report" if not blocked_reasons else "blocked",
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        higher_order_agent_os_ready=ready or scenario == "operator-cockpit",
        objective_compiler_workflow_ready=objective.objective_compiler_workflow_ready,
        governed_live_connector_platform_ready=connectors.connectors_ready,
        tui_cockpit_ready=True,
        recursive_improvement_review_ready=True,
        plugin_ecosystem_skeleton_ready=True,
        remote_sandbox_contract_ready=True,
        tenant_auth_contract_ready=True,
        eval_dashboard_contract_ready=True,
        persistent_audit_contract_ready=True,
        operator_commands=_operator_commands() if scenario == "operator-cockpit" else (),
        tui_panels=_tui_panels() if scenario == "operator-cockpit" else (),
        plugin_contracts=_plugin_contracts(),
        sandbox_contracts=_sandbox_contracts(),
        auth_contracts=_auth_contracts(),
        learning_contracts=_learning_contracts(),
        remote_sandbox_enabled=False,
        multi_user_hosted_enabled=False,
        unattended_execution_enabled=False,
        memory_auto_promotion=False,
        production_ready=False,
        network_opened=objective.network_opened or connectors.network_opened,
        credential_material_accessed=(
            objective.credential_material_accessed or connectors.credential_material_accessed
        ),
        external_delivery_opened=objective.external_delivery_opened or connectors.external_delivery_opened,
        handler_executed=False,
        live_production_claimed=objective.live_production_claimed or connectors.live_production_claimed,
        no_secret_echo=objective.no_secret_echo and connectors.no_secret_echo,
    )


def _blocked_reasons(scenario: HigherOrderAgentOsScenario) -> tuple[str, ...]:
    if scenario != "public-boundary":
        return ()
    return (
        "production_live_execution_not_enabled",
        "remote_sandbox_not_enabled",
        "multi_user_hosted_not_enabled",
        "unattended_execution_not_enabled",
        "memory_auto_promotion_not_enabled",
    )


def _operator_commands() -> tuple[str, ...]:
    return (
        "zeus objective-compile-workflow --objective \"제우스야, 이 목표를 workflow로 컴파일해줘.\" --requires-code --task-count 4 --json",
        "zeus governed-live-connectors --scenario trusted-local-smoke --json",
        "zeus higher-order-agent-os --scenario public-boundary --json",
        "zeus release-gated-ulw --target-version v6.0.0 --json",
    )


def _tui_panels() -> tuple[str, ...]:
    return (
        "objective",
        "workflow",
        "authority",
        "connectors",
        "evidence",
        "learning",
        "security",
    )


def _plugin_contracts() -> tuple[str, ...]:
    return (
        "plugin_manifest_required",
        "permission_declaration_required",
        "signature_or_hash_verification_required",
        "untrusted_plugin_quarantine_required",
    )


def _sandbox_contracts() -> tuple[str, ...]:
    return (
        "remote_backend_interface_defined",
        "docker_ssh_backends_default_denied",
        "network_mount_secret_policy_required",
        "host_docker_socket_forbidden",
    )


def _auth_contracts() -> tuple[str, ...]:
    return (
        "tenant_principal_role_scope_model_defined",
        "api_key_auth_contract_defined",
        "loopback_default_for_hosted_surface",
        "persistent_audit_required",
    )


def _learning_contracts() -> tuple[str, ...]:
    return (
        "error_ledger_candidate_only",
        "eval_registry_required",
        "skill_candidate_review_required",
        "memory_ontology_promotion_requires_review",
    )
