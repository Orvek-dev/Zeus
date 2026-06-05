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
    "v1.0.0-rc.1",
    "v1.0.0-rc.2",
    "v1.0.0-rc.3",
    "v1.0.0-rc.4",
    "v1.0.0-rc.5",
    "v1.0.0-rc.6",
    "v1.0.0-rc.7",
    "v1.0.0-rc.8",
    "v1.0.0-rc.9",
    "v1.0.0",
)
_STAGE_BY_VERSION: Final[dict[str, str]] = {
    "v0.6.0": "live_spine",
    "v0.7.0": "tool_limbs",
    "v0.8.0": "platform_surface",
    "v0.9.0": "memory_ontology",
    "v0.10.0": "adaptive_zeus",
    "v1.0.0-rc": "live_beta_candidate",
    "v1.0.0-rc.1": "production_foundation",
    "v1.0.0-rc.2": "provider_live_api",
    "v1.0.0-rc.3": "mcp_live_server",
    "v1.0.0-rc.4": "gateway_live_delivery",
    "v1.0.0-rc.5": "sandbox_terminal_live",
    "v1.0.0-rc.6": "memory_privacy_live",
    "v1.0.0-rc.7": "provider_live_optin",
    "v1.0.0-rc.8": "provider_owned_client_live",
    "v1.0.0-rc.9": "mcp_owned_client_live",
    "v1.0.0": "stable_governed_live_platform",
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
    platform_surface_contract_available: bool = False
    cli_surface_contract_available: bool = False
    api_server_contract_available: bool = False
    gateway_surface_contract_available: bool = False
    acp_adapter_contract_available: bool = False
    batch_runner_contract_available: bool = False
    python_library_contract_available: bool = False
    platform_surface_ready: bool = False
    memory_ontology_contract_available: bool = False
    memory_graph_contract_available: bool = False
    llm_wiki_contract_available: bool = False
    ontology_review_contract_available: bool = False
    skill_learning_memory_contract_available: bool = False
    retention_policy_contract_available: bool = False
    memory_ontology_ready: bool = False
    adaptive_zeus_contract_available: bool = False
    dynamic_workflow_contract_available: bool = False
    pattern_router_contract_available: bool = False
    critique_checkpoint_contract_available: bool = False
    workflow_learning_contract_available: bool = False
    trajectory_eval_contract_available: bool = False
    adaptive_zeus_ready: bool = False
    live_beta_candidate_contract_available: bool = False
    live_readiness_contract_available: bool = False
    live_optin_smoke_contract_available: bool = False
    live_cockpit_contract_available: bool = False
    live_beta_activation_contract_available: bool = False
    rc_closeout_contract_available: bool = False
    live_beta_candidate_ready: bool = False
    production_foundation_contract_available: bool = False
    identity_runtime_available: bool = False
    auth_runtime_available: bool = False
    approval_runtime_available: bool = False
    credential_binding_runtime_available: bool = False
    secret_resolver_runtime_available: bool = False
    audit_runtime_available: bool = False
    sandbox_policy_available: bool = False
    production_foundation_ready: bool = False
    provider_live_api_contract_available: bool = False
    provider_loopback_http_available: bool = False
    provider_credentialed_http_available: bool = False
    provider_external_transport_available: bool = False
    provider_owned_client_available: bool = False
    provider_direct_adapter_available: bool = False
    provider_live_api_ready: bool = False
    mcp_live_server_contract_available: bool = False
    mcp_catalog_available: bool = False
    mcp_activation_policy_available: bool = False
    mcp_request_envelope_available: bool = False
    mcp_loopback_http_available: bool = False
    mcp_credentialed_http_available: bool = False
    mcp_remote_server_available: bool = False
    mcp_resources_enabled: bool = False
    mcp_prompts_enabled: bool = False
    mcp_live_server_ready: bool = False
    gateway_live_delivery_contract_available: bool = False
    gateway_settings_available: bool = False
    gateway_pairing_available: bool = False
    gateway_delivery_envelope_available: bool = False
    gateway_delivery_body_available: bool = False
    gateway_loopback_transport_available: bool = False
    gateway_loopback_http_available: bool = False
    gateway_external_delivery_available: bool = False
    gateway_webhook_available: bool = False
    gateway_live_delivery_ready: bool = False
    sandbox_terminal_live_contract_available: bool = False
    terminal_facade_available: bool = False
    sandbox_dispatch_facade_available: bool = False
    tool_sandbox_executor_available: bool = False
    browser_dispatch_guard_available: bool = False
    local_terminal_smoke_available: bool = False
    local_sandbox_execution_ready: bool = False
    remote_sandbox_available: bool = False
    docker_backend_available: bool = False
    ssh_backend_available: bool = False
    browser_live_navigation_available: bool = False
    memory_privacy_live_contract_available: bool = False
    local_memory_store_available: bool = False
    sqlite_backend_available: bool = False
    retention_delete_available: bool = False
    secret_quarantine_available: bool = False
    pii_redaction_available: bool = False
    cross_session_search_default_denied: bool = False
    local_privacy_ready: bool = False
    provider_live_optin_contract_available: bool = False
    provider_external_receipt_available: bool = False
    remote_transport_policy_available: bool = False
    remote_executor_preflight_available: bool = False
    provider_live_optin_ready: bool = False
    provider_owned_client_live_contract_available: bool = False
    provider_owned_client_transport_available: bool = False
    owned_client_adapter_available: bool = False
    provider_owned_client_live_ready: bool = False
    mcp_owned_client_live_contract_available: bool = False
    mcp_owned_client_transport_available: bool = False
    mcp_owned_client_adapter_available: bool = False
    mcp_owned_client_live_ready: bool = False
    stable_release_contract_available: bool = False
    stable_governed_live_platform_ready: bool = False
    stable_public_release_ready: bool = False
    production_ready: bool = False
    workflow_self_modification: bool = False
    workflow_memory_auto_write: bool = False
    memory_auto_promotion: bool = False
    ontology_auto_promotion: bool = False
    wiki_page_update_written: bool = False
    active_rule_written: bool = False
    authority_widened: bool = False
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
    platform_surface_contract_available = normalized_version == "v0.8.0" and "unknown_target_version" not in blocked_reasons
    memory_ontology_contract_available = normalized_version == "v0.9.0" and "unknown_target_version" not in blocked_reasons
    adaptive_zeus_contract_available = normalized_version == "v0.10.0" and "unknown_target_version" not in blocked_reasons
    live_beta_candidate_contract_available = normalized_version == "v1.0.0-rc" and "unknown_target_version" not in blocked_reasons
    production_foundation_contract_available = (
        normalized_version == "v1.0.0-rc.1" and "unknown_target_version" not in blocked_reasons
    )
    provider_live_api_contract_available = (
        normalized_version == "v1.0.0-rc.2" and "unknown_target_version" not in blocked_reasons
    )
    mcp_live_server_contract_available = (
        normalized_version == "v1.0.0-rc.3" and "unknown_target_version" not in blocked_reasons
    )
    gateway_live_delivery_contract_available = (
        normalized_version == "v1.0.0-rc.4" and "unknown_target_version" not in blocked_reasons
    )
    sandbox_terminal_live_contract_available = (
        normalized_version == "v1.0.0-rc.5" and "unknown_target_version" not in blocked_reasons
    )
    memory_privacy_live_contract_available = (
        normalized_version == "v1.0.0-rc.6" and "unknown_target_version" not in blocked_reasons
    )
    provider_live_optin_contract_available = (
        normalized_version == "v1.0.0-rc.7" and "unknown_target_version" not in blocked_reasons
    )
    provider_owned_client_live_contract_available = (
        normalized_version == "v1.0.0-rc.8" and "unknown_target_version" not in blocked_reasons
    )
    mcp_owned_client_live_contract_available = (
        normalized_version == "v1.0.0-rc.9" and "unknown_target_version" not in blocked_reasons
    )
    stable_release_contract_available = (
        normalized_version == "v1.0.0" and "unknown_target_version" not in blocked_reasons
    )
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
        required_checkpoint_evidence=_required_checkpoint_evidence(normalized_version),
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
        platform_surface_contract_available=platform_surface_contract_available,
        cli_surface_contract_available=platform_surface_contract_available,
        api_server_contract_available=platform_surface_contract_available,
        gateway_surface_contract_available=platform_surface_contract_available,
        acp_adapter_contract_available=platform_surface_contract_available,
        batch_runner_contract_available=platform_surface_contract_available,
        python_library_contract_available=platform_surface_contract_available,
        platform_surface_ready=False,
        memory_ontology_contract_available=memory_ontology_contract_available,
        memory_graph_contract_available=memory_ontology_contract_available,
        llm_wiki_contract_available=memory_ontology_contract_available,
        ontology_review_contract_available=memory_ontology_contract_available,
        skill_learning_memory_contract_available=memory_ontology_contract_available,
        retention_policy_contract_available=memory_ontology_contract_available,
        memory_ontology_ready=False,
        adaptive_zeus_contract_available=adaptive_zeus_contract_available,
        dynamic_workflow_contract_available=adaptive_zeus_contract_available,
        pattern_router_contract_available=adaptive_zeus_contract_available,
        critique_checkpoint_contract_available=adaptive_zeus_contract_available,
        workflow_learning_contract_available=adaptive_zeus_contract_available,
        trajectory_eval_contract_available=adaptive_zeus_contract_available,
        adaptive_zeus_ready=False,
        live_beta_candidate_contract_available=live_beta_candidate_contract_available,
        live_readiness_contract_available=live_beta_candidate_contract_available,
        live_optin_smoke_contract_available=live_beta_candidate_contract_available,
        live_cockpit_contract_available=live_beta_candidate_contract_available,
        live_beta_activation_contract_available=live_beta_candidate_contract_available,
        rc_closeout_contract_available=live_beta_candidate_contract_available,
        live_beta_candidate_ready=False,
        production_foundation_contract_available=production_foundation_contract_available,
        identity_runtime_available=production_foundation_contract_available,
        auth_runtime_available=production_foundation_contract_available,
        approval_runtime_available=production_foundation_contract_available,
        credential_binding_runtime_available=production_foundation_contract_available,
        secret_resolver_runtime_available=production_foundation_contract_available,
        audit_runtime_available=production_foundation_contract_available,
        sandbox_policy_available=production_foundation_contract_available,
        production_foundation_ready=False,
        provider_live_api_contract_available=provider_live_api_contract_available,
        provider_loopback_http_available=provider_live_api_contract_available,
        provider_credentialed_http_available=provider_live_api_contract_available,
        provider_external_transport_available=provider_live_optin_contract_available,
        provider_owned_client_available=provider_live_api_contract_available or provider_owned_client_live_contract_available,
        provider_direct_adapter_available=provider_live_api_contract_available,
        provider_live_api_ready=False,
        mcp_live_server_contract_available=mcp_live_server_contract_available,
        mcp_catalog_available=mcp_live_server_contract_available,
        mcp_activation_policy_available=mcp_live_server_contract_available,
        mcp_request_envelope_available=mcp_live_server_contract_available,
        mcp_loopback_http_available=mcp_live_server_contract_available,
        mcp_credentialed_http_available=mcp_live_server_contract_available,
        mcp_remote_server_available=False,
        mcp_resources_enabled=False,
        mcp_prompts_enabled=False,
        mcp_live_server_ready=False,
        gateway_live_delivery_contract_available=gateway_live_delivery_contract_available,
        gateway_settings_available=gateway_live_delivery_contract_available,
        gateway_pairing_available=gateway_live_delivery_contract_available,
        gateway_delivery_envelope_available=gateway_live_delivery_contract_available,
        gateway_delivery_body_available=gateway_live_delivery_contract_available,
        gateway_loopback_transport_available=gateway_live_delivery_contract_available,
        gateway_loopback_http_available=gateway_live_delivery_contract_available,
        gateway_external_delivery_available=False,
        gateway_webhook_available=False,
        gateway_live_delivery_ready=False,
        sandbox_terminal_live_contract_available=sandbox_terminal_live_contract_available,
        terminal_facade_available=sandbox_terminal_live_contract_available,
        sandbox_dispatch_facade_available=sandbox_terminal_live_contract_available,
        tool_sandbox_executor_available=sandbox_terminal_live_contract_available,
        browser_dispatch_guard_available=sandbox_terminal_live_contract_available,
        local_terminal_smoke_available=sandbox_terminal_live_contract_available,
        local_sandbox_execution_ready=False,
        remote_sandbox_available=False,
        docker_backend_available=False,
        ssh_backend_available=False,
        browser_live_navigation_available=False,
        memory_privacy_live_contract_available=memory_privacy_live_contract_available,
        local_memory_store_available=memory_privacy_live_contract_available,
        sqlite_backend_available=memory_privacy_live_contract_available,
        retention_delete_available=memory_privacy_live_contract_available,
        secret_quarantine_available=memory_privacy_live_contract_available,
        pii_redaction_available=memory_privacy_live_contract_available,
        cross_session_search_default_denied=memory_privacy_live_contract_available,
        local_privacy_ready=False,
        provider_live_optin_contract_available=provider_live_optin_contract_available,
        provider_external_receipt_available=provider_live_optin_contract_available,
        remote_transport_policy_available=(
            provider_live_optin_contract_available
            or provider_owned_client_live_contract_available
            or mcp_owned_client_live_contract_available
        ),
        remote_executor_preflight_available=(
            provider_live_optin_contract_available
            or provider_owned_client_live_contract_available
            or mcp_owned_client_live_contract_available
        ),
        provider_live_optin_ready=False,
        provider_owned_client_live_contract_available=provider_owned_client_live_contract_available,
        provider_owned_client_transport_available=provider_owned_client_live_contract_available,
        owned_client_adapter_available=provider_owned_client_live_contract_available,
        provider_owned_client_live_ready=False,
        mcp_owned_client_live_contract_available=mcp_owned_client_live_contract_available,
        mcp_owned_client_transport_available=mcp_owned_client_live_contract_available,
        mcp_owned_client_adapter_available=mcp_owned_client_live_contract_available,
        mcp_owned_client_live_ready=False,
        stable_release_contract_available=stable_release_contract_available,
        stable_governed_live_platform_ready=stable_release_contract_available,
        stable_public_release_ready=stable_release_contract_available,
        production_ready=False,
        workflow_self_modification=False,
        workflow_memory_auto_write=False,
        memory_auto_promotion=False,
        ontology_auto_promotion=False,
        wiki_page_update_written=False,
        active_rule_written=False,
        authority_widened=False,
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
    elif target_version not in {
        "v0.6.0",
        "v0.7.0",
        "v0.8.0",
        "v0.9.0",
        "v0.10.0",
        "v1.0.0-rc",
        "v1.0.0-rc.1",
        "v1.0.0-rc.2",
        "v1.0.0-rc.3",
        "v1.0.0-rc.4",
        "v1.0.0-rc.5",
        "v1.0.0-rc.6",
        "v1.0.0-rc.7",
        "v1.0.0-rc.8",
        "v1.0.0-rc.9",
        "v1.0.0",
    }:
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


def _required_checkpoint_evidence(target_version: str) -> tuple[str, ...]:
    if target_version == "v1.0.0":
        return (
            "stable_governed_live_platform_manual_qa",
            "stable_release_cli_library_regression_manual_qa",
            "stable_release_security_boundary_review",
            "stable_release_package_build",
            "stable_release_remote_ci_success",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v1.0.0-rc.9":
        return (
            "mcp_owned_client_live_release_gate_manual_qa",
            "mcp_owned_client_live_missing_optin_manual_qa",
            "mcp_owned_client_live_missing_secret_manual_qa",
            "mcp_owned_client_live_smoke_manual_qa",
            "mcp_owned_client_live_cli_library_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v1.0.0-rc.8":
        return (
            "provider_owned_client_live_release_gate_manual_qa",
            "provider_owned_client_live_missing_optin_manual_qa",
            "provider_owned_client_live_missing_secret_manual_qa",
            "provider_owned_client_live_smoke_manual_qa",
            "provider_owned_client_live_cli_library_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v1.0.0-rc.7":
        return (
            "provider_live_optin_release_gate_manual_qa",
            "provider_live_optin_missing_optin_manual_qa",
            "provider_live_optin_unallowlisted_manual_qa",
            "provider_live_optin_missing_secret_manual_qa",
            "provider_live_optin_external_receipt_manual_qa",
            "provider_live_optin_cli_library_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v1.0.0-rc.6":
        return (
            "memory_privacy_live_release_gate_manual_qa",
            "memory_privacy_live_local_smoke_manual_qa",
            "memory_privacy_live_secret_quarantine_manual_qa",
            "memory_privacy_live_delete_retention_manual_qa",
            "memory_privacy_live_promotion_block_manual_qa",
            "memory_privacy_live_cli_library_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v1.0.0-rc.5":
        return (
            "sandbox_terminal_live_release_gate_manual_qa",
            "sandbox_terminal_live_local_smoke_manual_qa",
            "sandbox_terminal_live_blocked_network_manual_qa",
            "sandbox_terminal_live_blocked_remote_manual_qa",
            "sandbox_terminal_live_cli_library_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v1.0.0-rc.4":
        return (
            "gateway_live_delivery_release_gate_manual_qa",
            "gateway_live_delivery_loopback_manual_qa",
            "gateway_live_delivery_missing_secret_manual_qa",
            "gateway_live_delivery_blocked_target_manual_qa",
            "gateway_live_delivery_cli_library_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v1.0.0-rc.3":
        return (
            "mcp_live_server_release_gate_manual_qa",
            "mcp_live_server_loopback_manual_qa",
            "mcp_live_server_missing_secret_manual_qa",
            "mcp_live_server_prompt_injection_manual_qa",
            "mcp_live_server_cli_library_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v1.0.0-rc.2":
        return (
            "provider_live_api_release_gate_manual_qa",
            "provider_live_api_loopback_manual_qa",
            "provider_live_api_missing_secret_manual_qa",
            "provider_live_api_cli_library_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v1.0.0-rc.1":
        return (
            "production_foundation_release_gate_manual_qa",
            "production_foundation_security_control_manual_qa",
            "production_foundation_secret_boundary_manual_qa",
            "production_foundation_cli_library_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v1.0.0-rc":
        return (
            "live_beta_candidate_release_gate_manual_qa",
            "live_beta_candidate_smoke_manual_qa",
            "live_beta_candidate_blocked_boundary_manual_qa",
            "live_beta_candidate_secret_boundary_manual_qa",
            "rc_adjacent_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v0.10.0":
        return (
            "adaptive_zeus_release_gate_manual_qa",
            "adaptive_zeus_pattern_selection_manual_qa",
            "adaptive_zeus_secret_boundary_manual_qa",
            "adaptive_zeus_adjacent_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v0.9.0":
        return (
            "memory_ontology_release_gate_manual_qa",
            "memory_ontology_local_store_manual_qa",
            "memory_ontology_secret_boundary_manual_qa",
            "memory_ontology_adjacent_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v0.8.0":
        return (
            "platform_surface_release_gate_manual_qa",
            "platform_surface_gateway_manual_qa",
            "platform_surface_secret_boundary_manual_qa",
            "platform_surface_adjacent_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    if target_version == "v0.7.0":
        return (
            "tool_limbs_contract_manual_qa",
            "tool_limbs_secret_boundary_manual_qa",
            "tool_limbs_adjacent_regression_manual_qa",
            "red_green_tests_captured",
            "manual_qa_evidence_captured",
            "independent_review_approved",
            "github_release_checkpoint_complete",
        )
    return (
        "provider_loopback_manual_qa",
        "mcp_loopback_manual_qa",
        "approval_lease_boundary_review",
        "red_green_tests_captured",
        "manual_qa_evidence_captured",
        "independent_review_approved",
        "github_release_checkpoint_complete",
    )


def _has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
