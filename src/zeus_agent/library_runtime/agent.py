from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

from zeus_agent.approval_cockpit_runtime import ApprovalCockpitRuntime
from zeus_agent.approval_receipt_runtime import ApprovalReceiptResult
from zeus_agent.approval_receipt_runtime import ApprovalReceiptRuntime
from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.entry_runtime import ZeusChatRuntime, default_zeus_home
from zeus_agent.gateway_cockpit_runtime import GatewayCockpitRuntime
from zeus_agent.gateway_live_delivery_runtime import build_gateway_live_delivery_contract
from zeus_agent.gateway_pairing_runtime import GatewayPairingRuntime
from zeus_agent.gateway_settings_runtime import GatewaySettingsRuntime
from zeus_agent.live_beta_runtime import LiveBetaActivationRequest, LiveBetaActivationRuntime
from zeus_agent.live_beta_candidate_runtime import build_live_beta_candidate_contract
from zeus_agent.mcp_live_server_runtime import build_mcp_live_server_contract
from zeus_agent.production_foundation_runtime import build_production_foundation_contract
from zeus_agent.provider_live_api_runtime import build_provider_live_api_contract
from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionRuntime
from zeus_agent.live_dry_run_runtime import LiveDryRunRuntime
from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationRuntime
from zeus_agent.live_execution_authorization_runtime import LiveExecutionAuthorizationResult
from zeus_agent.live_execution_readiness_runtime import (
    LiveExecutionReadinessResult,
    LiveExecutionReadinessRuntime,
)
from zeus_agent.live_execute_runtime import LiveExecutePlanRequest, LiveExecutePlanRuntime
from zeus_agent.live_execute_runtime import LiveExecutePlanResult
from zeus_agent.live_execution_bundle_review_runtime import LiveExecutionBundleReviewRuntime
from zeus_agent.live_execution_bundle_review_runtime import LiveExecutionBundleReviewResult
from zeus_agent.live_execution_bundle_runtime import LiveExecutionBundleRuntime
from zeus_agent.live_execution_bundle_runtime import LiveExecutionBundleResult
from zeus_agent.live_execution_status_runtime import LiveExecutionStatusRuntime
from zeus_agent.live_execution_status_runtime import LiveExecutionStatusResult
from zeus_agent.live_execution_registry_runtime import LiveExecutionRegistryRuntime
from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseRuntime
from zeus_agent.live_executor_release_runtime import LiveExecutorReleaseResult
from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterRuntime
from zeus_agent.live_gateway_adapter_runtime import LiveGatewayAdapterResult
from zeus_agent.live_gateway_delivery_body_runtime import LiveGatewayDeliveryBodyResult
from zeus_agent.live_gateway_delivery_body_runtime import LiveGatewayDeliveryBodyRuntime
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryRuntime
from zeus_agent.live_gateway_delivery_runtime import LiveGatewayDeliveryResult
from zeus_agent.live_gateway_credentialed_http_runtime import (
    LiveGatewayCredentialedHttpResult,
    LiveGatewayCredentialedHttpRuntime,
)
from zeus_agent.live_gateway_external_transport_runtime import LiveGatewayExternalClientResult
from zeus_agent.live_gateway_external_transport_runtime import LiveGatewayExternalTransportResult
from zeus_agent.live_gateway_external_transport_runtime import LiveGatewayExternalTransportRuntime
from zeus_agent.live_gateway_delivery_adapter_runtime import LiveGatewayDeliveryAdapterReceipt
from zeus_agent.live_gateway_delivery_adapter_runtime import LiveGatewayDeliveryAdapterResult
from zeus_agent.live_gateway_delivery_adapter_runtime import LiveGatewayDeliveryAdapterRuntime
from zeus_agent.live_gateway_delivery_adapter_runtime import StaticGatewayDeliveryAdapterClient
from zeus_agent.live_gateway_owned_client_transport_runtime import LiveGatewayOwnedClientReceipt
from zeus_agent.live_gateway_owned_client_transport_runtime import LiveGatewayOwnedClientTransportResult
from zeus_agent.live_gateway_owned_client_transport_runtime import LiveGatewayOwnedClientTransportRuntime
from zeus_agent.live_gateway_owned_client_transport_runtime import StaticGatewayOwnedClient
from zeus_agent.live_gateway_execution_runtime import LiveGatewayExecutionRuntime
from zeus_agent.live_gateway_http_transport_runtime import LiveGatewayHttpTransportRuntime
from zeus_agent.live_gateway_http_transport_runtime import LiveGatewayHttpTransportResult
from zeus_agent.live_gateway_loopback_transport_runtime import LiveGatewayLoopbackTransportRuntime
from zeus_agent.live_gateway_loopback_transport_runtime import LiveGatewayLoopbackTransportResult
from zeus_agent.live_handoff_runtime import LiveHandoffRequest, LiveHandoffRuntime
from zeus_agent.live_loopback_executor_runtime import LiveLoopbackExecutorRuntime
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterRuntime
from zeus_agent.live_mcp_adapter_runtime import LiveMcpAdapterResult
from zeus_agent.live_mcp_activation_policy_runtime import LiveMcpActivationPolicyRuntime
from zeus_agent.live_mcp_execution_runtime import LiveMcpExecutionRuntime
from zeus_agent.live_mcp_credentialed_http_runtime import (
    LiveMcpCredentialedHttpResult,
    LiveMcpCredentialedHttpRuntime,
)
from zeus_agent.live_mcp_external_transport_runtime import LiveMcpExternalClientResult
from zeus_agent.live_mcp_external_transport_runtime import LiveMcpExternalTransportResult
from zeus_agent.live_mcp_external_transport_runtime import LiveMcpExternalTransportRuntime
from zeus_agent.live_mcp_remote_adapter_runtime import LiveMcpRemoteAdapterReceipt
from zeus_agent.live_mcp_remote_adapter_runtime import LiveMcpRemoteAdapterResult
from zeus_agent.live_mcp_remote_adapter_runtime import LiveMcpRemoteAdapterRuntime
from zeus_agent.live_mcp_remote_adapter_runtime import StaticMcpRemoteAdapterClient
from zeus_agent.live_mcp_owned_client_transport_runtime import LiveMcpOwnedClientReceipt
from zeus_agent.live_mcp_owned_client_transport_runtime import LiveMcpOwnedClientTransportResult
from zeus_agent.live_mcp_owned_client_transport_runtime import LiveMcpOwnedClientTransportRuntime
from zeus_agent.live_mcp_owned_client_transport_runtime import StaticMcpOwnedClient
from zeus_agent.live_mcp_http_transport_runtime import LiveMcpHttpTransportRuntime
from zeus_agent.live_mcp_http_transport_runtime import LiveMcpHttpTransportResult
from zeus_agent.live_mcp_loopback_transport_runtime import LiveMcpLoopbackTransportRuntime
from zeus_agent.live_mcp_loopback_transport_runtime import LiveMcpLoopbackTransportResult
from zeus_agent.live_mcp_request_body_runtime import LiveMcpRequestBodyResult
from zeus_agent.live_mcp_request_body_runtime import LiveMcpRequestBodyRuntime
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestRuntime
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofResult, LiveOperatorProofRuntime
from zeus_agent.live_preflight_runtime import LivePreflightRequest, LivePreflightRuntime
from zeus_agent.live_production_approval_runtime import LiveProductionApprovalRuntime
from zeus_agent.live_production_approval_runtime import LiveProductionApprovalResult
from zeus_agent.live_production_claim_runtime import LiveProductionClaimResult
from zeus_agent.live_production_claim_runtime import LiveProductionClaimRuntime
from zeus_agent.live_profile_runtime import LiveProfileRuntime
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterRuntime
from zeus_agent.live_provider_adapter_runtime import LiveProviderAdapterResult
from zeus_agent.live_provider_execution_runtime import LiveProviderExecutionRuntime
from zeus_agent.live_provider_http_transport_runtime import LiveProviderHttpTransportRuntime
from zeus_agent.live_provider_http_transport_runtime import LiveProviderHttpTransportResult
from zeus_agent.live_provider_external_transport_runtime import LiveProviderExternalClientResult
from zeus_agent.live_provider_external_transport_runtime import LiveProviderExternalTransportResult
from zeus_agent.live_provider_external_transport_runtime import LiveProviderExternalTransportRuntime
from zeus_agent.live_provider_direct_adapter_runtime import LiveProviderDirectAdapterReceipt
from zeus_agent.live_provider_direct_adapter_runtime import LiveProviderDirectAdapterResult
from zeus_agent.live_provider_direct_adapter_runtime import LiveProviderDirectAdapterRuntime
from zeus_agent.live_provider_direct_adapter_runtime import StaticProviderDirectAdapterClient
from zeus_agent.live_provider_credentialed_http_runtime import (
    LiveProviderCredentialedHttpResult,
    LiveProviderCredentialedHttpRuntime,
)
from zeus_agent.live_provider_owned_client_transport_runtime import LiveProviderOwnedClientReceipt
from zeus_agent.live_provider_owned_client_transport_runtime import LiveProviderOwnedClientTransportResult
from zeus_agent.live_provider_owned_client_transport_runtime import LiveProviderOwnedClientTransportRuntime
from zeus_agent.live_provider_owned_client_transport_runtime import StaticProviderOwnedClient
from zeus_agent.live_provider_loopback_transport_runtime import LiveProviderLoopbackTransportRuntime
from zeus_agent.live_provider_loopback_transport_runtime import LiveProviderLoopbackTransportResult
from zeus_agent.live_provider_request_body_runtime import LiveProviderRequestBodyResult
from zeus_agent.live_provider_request_body_runtime import LiveProviderRequestBodyRuntime
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffRuntime
from zeus_agent.live_remote_credential_handoff_runtime import LiveRemoteCredentialHandoffResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightRuntime
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyRuntime
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_provider_request_runtime import LiveProviderRequestRuntime
from zeus_agent.live_provider_request_runtime import LiveProviderRequestResult
from zeus_agent.live_readiness_runtime import LiveReadinessRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult
from zeus_agent.live_sealed_credential_runtime import LiveSealedCredentialRuntime
from zeus_agent.live_sealed_credential_runtime import StaticSealedCredentialConsumer
from zeus_agent.live_smoke_runtime import run_live_optin_smoke
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseRuntime
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseResult
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationResult
from zeus_agent.live_transport_activation_runtime import LiveTransportActivationRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditResult
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownResult
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownRuntime
from zeus_agent.live_transport_opt_in_runtime import LiveTransportOptInRuntime
from zeus_agent.live_transport_opt_in_runtime import LiveTransportOptInResult
from zeus_agent.library_runtime.growth_facade import GrowthFacadeMixin
from zeus_agent.library_runtime.live_research_facade import LiveResearchFacadeMixin
from zeus_agent.mcp_runtime import curated_mcp_catalog_payload
from zeus_agent.mcp_cockpit_runtime import McpCockpitRuntime
from zeus_agent.mcp_settings_runtime import McpSettingsRuntime
from zeus_agent.memory_cockpit_runtime import MemoryCockpitRuntime
from zeus_agent.memory_entry_runtime import MemoryEntryRuntime
from zeus_agent.memory_privacy_live_runtime import build_memory_privacy_live_contract
from zeus_agent.mcp_owned_client_live_runtime import build_mcp_owned_client_live_contract
from zeus_agent.model_cockpit_runtime import ModelCockpitRuntime
from zeus_agent.model_runtime import provider_catalog_payload
from zeus_agent.model_settings_runtime import ModelSettingsRuntime
from zeus_agent.objective_runtime import ObjectiveCompiler
from zeus_agent.orchestration_runtime import DynamicWorkflowCompiler, WorkflowCompileRequest
from zeus_agent.provider_live_optin_runtime import build_provider_live_optin_contract
from zeus_agent.provider_owned_client_live_runtime import build_provider_owned_client_live_contract
from zeus_agent.research_runtime import build_research_brief
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.runtime_cockpit import RuntimeCockpitRuntime
from zeus_agent.sandbox_terminal_live_runtime import build_sandbox_terminal_live_contract
from zeus_agent.security_cockpit_runtime import SecurityCockpitRuntime
from zeus_agent.secret_resolver_runtime import SecretResolverPlanRuntime
from zeus_agent.tool_runtime import native_tool_catalog_payload
from zeus_agent.tool_cockpit_runtime import ToolCockpitRuntime
from zeus_agent.setup_runtime import setup_apply
from zeus_agent.workflow_cockpit_runtime import WorkflowCockpitRuntime
from zeus_agent.work_entry_runtime import WorkEntryRuntime


class ZeusAgent(GrowthFacadeMixin, LiveResearchFacadeMixin):
    def __init__(self, *, home: Optional[Path] = None, profile: str = "chat") -> None:
        self.home = home or default_zeus_home()
        self.profile = profile
        self.live_production_claimed = False

    def chat(
        self,
        message: str,
        *,
        session_id: str = "default",
        provider_id: Optional[str] = None,
    ) -> dict[str, Any]:
        return ZeusChatRuntime(self.home).run_turn(
            message=message,
            session_id=session_id,
            provider_id=provider_id,
            profile=self.profile,
        ).to_payload()

    def model_preference(self) -> dict[str, Any]:
        return ModelSettingsRuntime(self.home).show().to_payload()

    def model_set(self, *, provider_ref: str, model_id: Optional[str] = None) -> dict[str, Any]:
        return ModelSettingsRuntime(self.home).set(provider_ref=provider_ref, model_id=model_id).to_payload()

    def setup_apply(
        self,
        *,
        provider_id: str = "fake",
        mcp: bool = False,
        mcp_servers: tuple[str, ...] = (),
        gateway: bool = False,
        gateway_adapter: Optional[str] = None,
        gateway_target: Optional[str] = None,
        local: bool = False,
    ) -> dict[str, Any]:
        return setup_apply(
            home=self.home,
            provider_id=provider_id,
            mcp=mcp,
            mcp_servers=mcp_servers,
            gateway=gateway,
            gateway_adapter=gateway_adapter,
            gateway_target=gateway_target,
            local=local,
        )

    def compile_objective(self, objective: str) -> dict[str, Any]:
        return ObjectiveCompiler().compile(objective).model_dump(mode="json")

    def workflow_compile(
        self,
        objective: str,
        *,
        task_count: int = 1,
        requires_code: bool = False,
        requires_research: bool = False,
        risk_level: str = "normal",
        evidence_target: str = "mneme.library.workflow",
    ) -> dict[str, Any]:
        request = WorkflowCompileRequest(
            objective=objective,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
            evidence_target=evidence_target,
        )
        return DynamicWorkflowCompiler().compile(request).model_dump(mode="json")

    def work_plan(
        self,
        objective: str,
        *,
        task_count: int = 1,
        requires_code: bool = False,
        requires_research: bool = False,
        risk_level: str = "normal",
        evidence_target: str = "mneme.work.entry",
        surface_id: Optional[str] = None,
        principal_id: str = "local.operator",
        delivery_target: Optional[str] = None,
        allowlisted_delivery_targets: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        return WorkEntryRuntime().plan(
            objective=objective,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
            evidence_target=evidence_target,
            surface_id=surface_id,
            principal_id=principal_id,
            delivery_target=delivery_target,
            allowlisted_delivery_targets=allowlisted_delivery_targets,
        ).to_payload()

    def research_brief(
        self,
        query: str,
        *,
        objective_id: str = "library.research",
    ) -> dict[str, Any]:
        return build_research_brief(objective_id=objective_id, query=query)

    def live_beta_activate(
        self,
        request: LiveBetaActivationRequest,
        *,
        lease: RuntimeLease,
        now: Optional[datetime] = None,
    ) -> dict[str, Any]:
        return LiveBetaActivationRuntime().activate(
            request,
            lease=lease,
            now=now,
        ).to_payload()

    def live_preflight(
        self,
        request: LivePreflightRequest,
        *,
        lease: RuntimeLease,
        now: Optional[datetime] = None,
        check_credentials: bool = False,
    ) -> dict[str, Any]:
        runtime = LivePreflightRuntime(home=self.home) if check_credentials else LivePreflightRuntime()
        return runtime.evaluate(
            request,
            lease=lease,
            now=now,
        ).to_payload()

    def live_handoff(self, request: LiveHandoffRequest) -> dict[str, Any]:
        return LiveHandoffRuntime().build(request).to_payload()

    def live_execute_plan(self, request: LiveExecutePlanRequest) -> dict[str, Any]:
        return LiveExecutePlanRuntime().plan(request).to_payload()

    def live_execution_readiness(self, execute_plan: dict[str, Any]) -> dict[str, Any]:
        return LiveExecutionReadinessRuntime().evaluate(
            LiveExecutePlanResult.model_validate(execute_plan),
        ).to_payload()

    def live_provider_generate(
        self,
        readiness: dict[str, Any],
        *,
        provider_kind: str,
        message: str,
    ) -> dict[str, Any]:
        return LiveProviderExecutionRuntime().generate(
            readiness=LiveExecutionReadinessResult.model_validate(readiness),
            provider_kind=provider_kind,
            message=message,
        ).to_payload()

    def live_mcp_invoke(
        self,
        readiness: dict[str, Any],
        *,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        return LiveMcpExecutionRuntime().invoke(
            readiness=LiveExecutionReadinessResult.model_validate(readiness),
            tool_name=tool_name,
            arguments=arguments,
        ).to_payload()

    def live_gateway_dispatch(
        self,
        readiness: dict[str, Any],
        *,
        adapter_id: str,
        target: str,
        message: str,
    ) -> dict[str, Any]:
        return LiveGatewayExecutionRuntime().dispatch(
            readiness=LiveExecutionReadinessResult.model_validate(readiness),
            adapter_id=adapter_id,
            target=target,
            message=message,
        ).to_payload()

    def live_transport_lease(
        self,
        readiness: dict[str, Any],
        lease: dict[str, Any],
        *,
        runtime_kind: str,
        capability_id: str,
        credential_scope: Optional[str],
        network_host: Optional[str],
        budget_required: int,
        evidence_target: str,
        now: Optional[datetime] = None,
    ) -> dict[str, Any]:
        return LiveTransportLeaseRuntime().bind(
            readiness=LiveExecutionReadinessResult.model_validate(readiness),
            lease=RuntimeLease.model_validate(lease),
            runtime_kind=runtime_kind,
            capability_id=capability_id,
            credential_scope=credential_scope,
            network_host=network_host,
            budget_required=budget_required,
            evidence_target=evidence_target,
            now=now,
        ).to_payload()

    def live_secret_material_check(
        self,
        transport_lease: dict[str, Any],
        *,
        secret_ref: str,
        allow_material_access: bool = False,
    ) -> dict[str, Any]:
        return LiveSecretMaterialRuntime().check(
            transport_lease=LiveTransportLeaseResult.model_validate(transport_lease),
            secret_ref=secret_ref,
            allow_material_access=allow_material_access,
        ).to_payload()

    def live_provider_request_envelope(
        self,
        transport_lease: dict[str, Any],
        secret_material: dict[str, Any],
        *,
        provider_kind: str,
        model_id: str,
        endpoint: str,
        message: str,
    ) -> dict[str, Any]:
        return LiveProviderRequestRuntime().prepare(
            transport_lease=LiveTransportLeaseResult.model_validate(transport_lease),
            secret_material=LiveSecretMaterialResult.model_validate(secret_material),
            provider_kind=provider_kind,
            model_id=model_id,
            endpoint=endpoint,
            message=message,
        ).to_payload()

    def live_provider_request_body(
        self,
        provider_envelope: dict[str, Any],
        *,
        message: str,
        body_ref: str,
    ) -> dict[str, Any]:
        return LiveProviderRequestBodyRuntime().materialize(
            provider_envelope=LiveProviderRequestResult.model_validate(provider_envelope),
            message=message,
            body_ref=body_ref,
        ).to_payload()

    def live_provider_credentialed_http(
        self,
        injection: dict[str, Any],
        secret_material: dict[str, Any],
        provider_envelope: dict[str, Any],
        request_body: dict[str, Any],
        *,
        transport_endpoint: str,
        timeout_ms: int,
        release_ref: str,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveProviderCredentialedHttpRuntime().execute(
            injection=LiveCredentialInjectionResult.model_validate(injection),
            secret_material=LiveSecretMaterialResult.model_validate(secret_material),
            provider_envelope=LiveProviderRequestResult.model_validate(provider_envelope),
            request_body=LiveProviderRequestBodyResult.model_validate(request_body),
            transport_endpoint=transport_endpoint,
            timeout_ms=timeout_ms,
            release_ref=release_ref,
            execution_ref=execution_ref,
        ).to_payload()

    def live_gateway_delivery_envelope(
        self,
        transport_lease: dict[str, Any],
        secret_material: dict[str, Any],
        *,
        adapter_id: str,
        target: str,
        message: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return LiveGatewayDeliveryRuntime().prepare(
            transport_lease=LiveTransportLeaseResult.model_validate(transport_lease),
            secret_material=LiveSecretMaterialResult.model_validate(secret_material),
            adapter_id=adapter_id,
            target=target,
            message=message,
            idempotency_key=idempotency_key,
        ).to_payload()

    def live_gateway_delivery_body(
        self,
        gateway_envelope: dict[str, Any],
        *,
        message: str,
        body_ref: str,
    ) -> dict[str, Any]:
        return LiveGatewayDeliveryBodyRuntime().materialize(
            gateway_envelope=LiveGatewayDeliveryResult.model_validate(gateway_envelope),
            message=message,
            body_ref=body_ref,
        ).to_payload()

    def live_gateway_credentialed_http(
        self,
        injection: dict[str, Any],
        secret_material: dict[str, Any],
        gateway_envelope: dict[str, Any],
        delivery_body: dict[str, Any],
        *,
        delivery_endpoint: str,
        timeout_ms: int,
        release_ref: str,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveGatewayCredentialedHttpRuntime().execute(
            injection=LiveCredentialInjectionResult.model_validate(injection),
            secret_material=LiveSecretMaterialResult.model_validate(secret_material),
            gateway_envelope=LiveGatewayDeliveryResult.model_validate(gateway_envelope),
            delivery_body=LiveGatewayDeliveryBodyResult.model_validate(delivery_body),
            delivery_endpoint=delivery_endpoint,
            timeout_ms=timeout_ms,
            release_ref=release_ref,
            execution_ref=execution_ref,
        ).to_payload()

    def live_mcp_request_envelope(
        self,
        transport_lease: dict[str, Any],
        secret_material: dict[str, Any],
        *,
        server_id: str,
        tool_name: str,
        endpoint: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        return LiveMcpRequestRuntime().prepare(
            transport_lease=LiveTransportLeaseResult.model_validate(transport_lease),
            secret_material=LiveSecretMaterialResult.model_validate(secret_material),
            server_id=server_id,
            tool_name=tool_name,
            endpoint=endpoint,
            arguments=arguments,
        ).to_payload()

    def live_mcp_request_body(
        self,
        mcp_envelope: dict[str, Any],
        *,
        arguments: dict[str, Any],
        body_ref: str,
    ) -> dict[str, Any]:
        return LiveMcpRequestBodyRuntime().materialize(
            mcp_envelope=LiveMcpRequestResult.model_validate(mcp_envelope),
            arguments=arguments,
            body_ref=body_ref,
        ).to_payload()

    def live_mcp_credentialed_http(
        self,
        injection: dict[str, Any],
        secret_material: dict[str, Any],
        mcp_envelope: dict[str, Any],
        request_body: dict[str, Any],
        *,
        transport_endpoint: str,
        timeout_ms: int,
        release_ref: str,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveMcpCredentialedHttpRuntime().execute(
            injection=LiveCredentialInjectionResult.model_validate(injection),
            secret_material=LiveSecretMaterialResult.model_validate(secret_material),
            mcp_envelope=LiveMcpRequestResult.model_validate(mcp_envelope),
            request_body=LiveMcpRequestBodyResult.model_validate(request_body),
            transport_endpoint=transport_endpoint,
            timeout_ms=timeout_ms,
            release_ref=release_ref,
            execution_ref=execution_ref,
        ).to_payload()

    def live_execution_bundle(
        self,
        provider_result: Optional[dict[str, Any]] = None,
        gateway_result: Optional[dict[str, Any]] = None,
        mcp_result: Optional[dict[str, Any]] = None,
        *,
        bundle_ref: str,
    ) -> dict[str, Any]:
        return LiveExecutionBundleRuntime().summarize(
            provider_result=(
                None
                if provider_result is None
                else LiveProviderCredentialedHttpResult.model_validate(provider_result)
            ),
            gateway_result=(
                None
                if gateway_result is None
                else LiveGatewayCredentialedHttpResult.model_validate(gateway_result)
            ),
            mcp_result=None if mcp_result is None else LiveMcpCredentialedHttpResult.model_validate(mcp_result),
            bundle_ref=bundle_ref,
        ).to_payload()

    def live_execution_bundle_review(
        self,
        bundle: dict[str, Any],
        *,
        reviewer_id: str,
        producer_id: str,
        evidence_ids: tuple[str, ...],
        risk_acknowledgements: tuple[str, ...],
    ) -> dict[str, Any]:
        return LiveExecutionBundleReviewRuntime().review(
            bundle=LiveExecutionBundleResult.model_validate(bundle),
            reviewer_id=reviewer_id,
            producer_id=producer_id,
            evidence_ids=evidence_ids,
            risk_acknowledgements=risk_acknowledgements,
        ).to_payload()

    def live_execution_status(
        self,
        bundle: Optional[dict[str, Any]] = None,
        review: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return LiveExecutionStatusRuntime().build(
            bundle=None if bundle is None else LiveExecutionBundleResult.model_validate(bundle),
            review=None if review is None else LiveExecutionBundleReviewResult.model_validate(review),
        ).to_payload()

    def live_execution_record(self, status: dict[str, Any], *, record_ref: str) -> dict[str, Any]:
        return LiveExecutionRegistryRuntime(self.home).record(
            status=LiveExecutionStatusResult.model_validate(status),
            record_ref=record_ref,
        ).to_payload()

    def live_execution_records(self) -> dict[str, Any]:
        return LiveExecutionRegistryRuntime(self.home).list().to_payload()

    def live_execution_record_delete(self, *, record_id: str, deletion_ref: str) -> dict[str, Any]:
        return LiveExecutionRegistryRuntime(self.home).delete(
            record_id=record_id,
            deletion_ref=deletion_ref,
        ).to_payload()

    def live_mcp_activation_policy(
        self,
        *,
        server_id: str,
        startup_requested: bool = False,
        resources_requested: bool = False,
        prompts_requested: bool = False,
        approval_ref: Optional[str] = None,
    ) -> dict[str, Any]:
        return LiveMcpActivationPolicyRuntime().plan(
            server_id=server_id,
            startup_requested=startup_requested,
            resources_requested=resources_requested,
            prompts_requested=prompts_requested,
            approval_ref=approval_ref,
        ).to_payload()

    def live_execution_authorization(
        self,
        *,
        envelope_kind: str,
        envelope: dict[str, Any],
        operator_proof: dict[str, Any],
        required_risks: tuple[str, ...],
    ) -> dict[str, Any]:
        return LiveExecutionAuthorizationRuntime().authorize(
            envelope_kind=envelope_kind,
            envelope=envelope,
            operator_proof=LiveOperatorProofResult.model_validate(operator_proof),
            required_risks=required_risks,
        ).to_payload()

    def live_executor_release(
        self,
        authorization: dict[str, Any],
        *,
        executor_kind: str,
        release_ref: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return LiveExecutorReleaseRuntime().release(
            authorization=LiveExecutionAuthorizationResult.model_validate(authorization),
            executor_kind=executor_kind,
            release_ref=release_ref,
            idempotency_key=idempotency_key,
        ).to_payload()

    def live_loopback_execute(
        self,
        release: dict[str, Any],
        *,
        envelope_kind: str,
        envelope: dict[str, Any],
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveLoopbackExecutorRuntime().execute(
            release=LiveExecutorReleaseResult.model_validate(release),
            envelope_kind=envelope_kind,
            envelope=envelope,
            execution_ref=execution_ref,
        ).to_payload()

    def live_provider_adapter_plan(
        self,
        release: dict[str, Any],
        *,
        provider_envelope: dict[str, Any],
        transport_mode: str,
        timeout_ms: int,
        retry_attempts: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return LiveProviderAdapterRuntime().plan(
            release=LiveExecutorReleaseResult.model_validate(release),
            provider_envelope=LiveProviderRequestResult.model_validate(provider_envelope),
            transport_mode=transport_mode,
            timeout_ms=timeout_ms,
            retry_attempts=retry_attempts,
            idempotency_key=idempotency_key,
        ).to_payload()

    def live_gateway_adapter_plan(
        self,
        release: dict[str, Any],
        *,
        gateway_envelope: dict[str, Any],
        transport_mode: str,
        timeout_ms: int,
        retry_attempts: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return LiveGatewayAdapterRuntime().plan(
            release=LiveExecutorReleaseResult.model_validate(release),
            gateway_envelope=LiveGatewayDeliveryResult.model_validate(gateway_envelope),
            transport_mode=transport_mode,
            timeout_ms=timeout_ms,
            retry_attempts=retry_attempts,
            idempotency_key=idempotency_key,
        ).to_payload()

    def live_mcp_adapter_plan(
        self,
        release: dict[str, Any],
        *,
        mcp_envelope: dict[str, Any],
        transport_mode: str,
        timeout_ms: int,
        retry_attempts: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return LiveMcpAdapterRuntime().plan(
            release=LiveExecutorReleaseResult.model_validate(release),
            mcp_envelope=LiveMcpRequestResult.model_validate(mcp_envelope),
            transport_mode=transport_mode,
            timeout_ms=timeout_ms,
            retry_attempts=retry_attempts,
            idempotency_key=idempotency_key,
        ).to_payload()

    def live_transport_opt_in(
        self,
        *,
        adapter_kind: str,
        adapter_plan: dict[str, Any],
        operator_proof: dict[str, Any],
        opt_in_ref: str,
        requested_transport_mode: str = "live",
    ) -> dict[str, Any]:
        return LiveTransportOptInRuntime().record(
            adapter_kind=adapter_kind,
            adapter_plan=_adapter_plan(adapter_kind=adapter_kind, payload=adapter_plan),
            operator_proof=LiveOperatorProofResult.model_validate(operator_proof),
            opt_in_ref=opt_in_ref,
            requested_transport_mode=requested_transport_mode,
        ).to_payload()

    def live_transport_activation_plan(
        self,
        opt_in: dict[str, Any],
        *,
        adapter_kind: str,
        adapter_plan: dict[str, Any],
        activation_ref: str,
    ) -> dict[str, Any]:
        return LiveTransportActivationRuntime().plan(
            opt_in=LiveTransportOptInResult.model_validate(opt_in),
            adapter_kind=adapter_kind,
            adapter_plan=_adapter_plan(adapter_kind=adapter_kind, payload=adapter_plan),
            activation_ref=activation_ref,
        ).to_payload()

    def live_provider_loopback_transport(
        self,
        activation: dict[str, Any],
        *,
        adapter_plan: dict[str, Any],
        provider_envelope: dict[str, Any],
        transport_kind: str,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveProviderLoopbackTransportRuntime().execute(
            activation=LiveTransportActivationResult.model_validate(activation),
            adapter_plan=LiveProviderAdapterResult.model_validate(adapter_plan),
            provider_envelope=LiveProviderRequestResult.model_validate(provider_envelope),
            transport_kind=transport_kind,
            execution_ref=execution_ref,
        ).to_payload()

    def live_provider_http_transport(
        self,
        activation: dict[str, Any],
        *,
        adapter_plan: dict[str, Any],
        provider_envelope: dict[str, Any],
        transport_kind: str,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveProviderHttpTransportRuntime().execute(
            activation=LiveTransportActivationResult.model_validate(activation),
            adapter_plan=LiveProviderAdapterResult.model_validate(adapter_plan),
            provider_envelope=LiveProviderRequestResult.model_validate(provider_envelope),
            transport_kind=transport_kind,
            execution_ref=execution_ref,
        ).to_payload()

    def live_gateway_loopback_transport(
        self,
        activation: dict[str, Any],
        *,
        adapter_plan: dict[str, Any],
        gateway_envelope: dict[str, Any],
        transport_kind: str,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveGatewayLoopbackTransportRuntime().execute(
            activation=LiveTransportActivationResult.model_validate(activation),
            adapter_plan=LiveGatewayAdapterResult.model_validate(adapter_plan),
            gateway_envelope=LiveGatewayDeliveryResult.model_validate(gateway_envelope),
            transport_kind=transport_kind,
            execution_ref=execution_ref,
        ).to_payload()

    def live_gateway_http_transport(
        self,
        activation: dict[str, Any],
        *,
        adapter_plan: dict[str, Any],
        gateway_envelope: dict[str, Any],
        delivery_endpoint: str,
        transport_kind: str,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveGatewayHttpTransportRuntime().execute(
            activation=LiveTransportActivationResult.model_validate(activation),
            adapter_plan=LiveGatewayAdapterResult.model_validate(adapter_plan),
            gateway_envelope=LiveGatewayDeliveryResult.model_validate(gateway_envelope),
            delivery_endpoint=delivery_endpoint,
            transport_kind=transport_kind,
            execution_ref=execution_ref,
        ).to_payload()

    def live_mcp_loopback_transport(
        self,
        activation: dict[str, Any],
        *,
        adapter_plan: dict[str, Any],
        mcp_envelope: dict[str, Any],
        transport_kind: str,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveMcpLoopbackTransportRuntime().execute(
            activation=LiveTransportActivationResult.model_validate(activation),
            adapter_plan=LiveMcpAdapterResult.model_validate(adapter_plan),
            mcp_envelope=LiveMcpRequestResult.model_validate(mcp_envelope),
            transport_kind=transport_kind,
            execution_ref=execution_ref,
        ).to_payload()

    def live_mcp_http_transport(
        self,
        activation: dict[str, Any],
        *,
        adapter_plan: dict[str, Any],
        mcp_envelope: dict[str, Any],
        transport_kind: str,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveMcpHttpTransportRuntime().execute(
            activation=LiveTransportActivationResult.model_validate(activation),
            adapter_plan=LiveMcpAdapterResult.model_validate(adapter_plan),
            mcp_envelope=LiveMcpRequestResult.model_validate(mcp_envelope),
            transport_kind=transport_kind,
            execution_ref=execution_ref,
        ).to_payload()

    def live_transport_audit(
        self,
        *,
        adapter_kind: str,
        execution: Optional[dict[str, Any]],
        audit_ref: str,
    ) -> dict[str, Any]:
        return LiveTransportAuditRuntime().audit(
            adapter_kind=adapter_kind,
            execution=_transport_execution(adapter_kind=adapter_kind, payload=execution),
            audit_ref=audit_ref,
        ).to_payload()

    def live_response_redact(
        self,
        audit: dict[str, Any],
        *,
        response_payload: dict[str, Any],
        response_ref: str,
    ) -> dict[str, Any]:
        return LiveResponseRedactionRuntime().redact(
            audit=LiveTransportAuditResult.model_validate(audit),
            response_payload=response_payload,
            response_ref=response_ref,
        ).to_payload()

    def live_remote_transport_policy(
        self,
        activation: Optional[dict[str, Any]],
        *,
        adapter_kind: str,
        adapter_plan: dict[str, Any],
        transport_kind: str,
        remote_target: str,
        allowed_remote_targets: tuple[str, ...],
        credential_scope: str,
        credential_binding_ref: str,
        policy_ref: str,
        audit_ref: str,
        redaction_ref: str,
        teardown_ref: str,
        production_review_ref: str,
        resources_requested: bool = False,
        prompts_requested: bool = False,
    ) -> dict[str, Any]:
        return LiveRemoteTransportPolicyRuntime().plan(
            activation=None if activation is None else LiveTransportActivationResult.model_validate(activation),
            adapter_kind=adapter_kind,
            adapter_plan=_adapter_plan(adapter_kind=adapter_kind, payload=adapter_plan),
            transport_kind=transport_kind,
            remote_target=remote_target,
            allowed_remote_targets=allowed_remote_targets,
            credential_scope=credential_scope,
            credential_binding_ref=credential_binding_ref,
            policy_ref=policy_ref,
            audit_ref=audit_ref,
            redaction_ref=redaction_ref,
            teardown_ref=teardown_ref,
            production_review_ref=production_review_ref,
            resources_requested=resources_requested,
            prompts_requested=prompts_requested,
        ).to_payload()

    def live_remote_credential_handoff(
        self,
        policy: dict[str, Any],
        secret_material: dict[str, Any],
        *,
        handoff_ref: str,
        auth_scheme: str = "bearer",
        header_name: str = "Authorization",
    ) -> dict[str, Any]:
        return LiveRemoteCredentialHandoffRuntime().prepare(
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            secret_material=LiveSecretMaterialResult.model_validate(secret_material),
            handoff_ref=handoff_ref,
            auth_scheme=auth_scheme,
            header_name=header_name,
        ).to_payload()

    def live_remote_executor_preflight(
        self,
        policy: dict[str, Any],
        handoff: dict[str, Any],
        *,
        executor_kind: str,
        executor_ref: str,
        idempotency_key: str,
        teardown_ref: str,
        timeout_ms: int = 1500,
        retry_attempts: int = 0,
    ) -> dict[str, Any]:
        return LiveRemoteExecutorPreflightRuntime().plan(
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            handoff=LiveRemoteCredentialHandoffResult.model_validate(handoff),
            executor_kind=executor_kind,
            executor_ref=executor_ref,
            idempotency_key=idempotency_key,
            teardown_ref=teardown_ref,
            timeout_ms=timeout_ms,
            retry_attempts=retry_attempts,
        ).to_payload()

    def live_credential_injection(
        self,
        claim: dict[str, Any],
        policy: dict[str, Any],
        preflight: dict[str, Any],
        handoff: dict[str, Any],
        secret_material: dict[str, Any],
        *,
        adapter_kind: str,
        injection_ref: str,
    ) -> dict[str, Any]:
        return LiveCredentialInjectionRuntime().prepare(
            adapter_kind=adapter_kind,
            claim=LiveProductionClaimResult.model_validate(claim),
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            preflight=LiveRemoteExecutorPreflightResult.model_validate(preflight),
            handoff=LiveRemoteCredentialHandoffResult.model_validate(handoff),
            secret_material=LiveSecretMaterialResult.model_validate(secret_material),
            injection_ref=injection_ref,
        ).to_payload()

    def live_sealed_credential_release(
        self,
        injection: dict[str, Any],
        secret_material: dict[str, Any],
        *,
        consumer_ref: str,
        release_ref: str,
    ) -> dict[str, Any]:
        return LiveSealedCredentialRuntime().release(
            injection=LiveCredentialInjectionResult.model_validate(injection),
            secret_material=LiveSecretMaterialResult.model_validate(secret_material),
            consumer=StaticSealedCredentialConsumer(consumer_ref),
            release_ref=release_ref,
        ).to_payload()

    def live_provider_external_transport(
        self,
        policy: dict[str, Any],
        preflight: dict[str, Any],
        provider_envelope: dict[str, Any],
        client_result: dict[str, Any],
        *,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveProviderExternalTransportRuntime().execute(
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            preflight=LiveRemoteExecutorPreflightResult.model_validate(preflight),
            provider_envelope=LiveProviderRequestResult.model_validate(provider_envelope),
            client_result=LiveProviderExternalClientResult.model_validate(client_result),
            execution_ref=execution_ref,
        ).to_payload()

    def live_provider_owned_client_transport(
        self,
        policy: dict[str, Any],
        preflight: dict[str, Any],
        handoff: dict[str, Any],
        provider_envelope: dict[str, Any],
        client_receipt: dict[str, Any],
        *,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveProviderOwnedClientTransportRuntime().execute(
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            preflight=LiveRemoteExecutorPreflightResult.model_validate(preflight),
            handoff=LiveRemoteCredentialHandoffResult.model_validate(handoff),
            provider_envelope=LiveProviderRequestResult.model_validate(provider_envelope),
            client=StaticProviderOwnedClient(LiveProviderOwnedClientReceipt.model_validate(client_receipt)),
            execution_ref=execution_ref,
        ).to_payload()

    def live_provider_direct_adapter(
        self,
        claim: dict[str, Any],
        policy: dict[str, Any],
        preflight: dict[str, Any],
        handoff: dict[str, Any],
        credential_injection: dict[str, Any],
        provider_envelope: dict[str, Any],
        client_receipt: dict[str, Any],
        *,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveProviderDirectAdapterRuntime().execute(
            claim=LiveProductionClaimResult.model_validate(claim),
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            preflight=LiveRemoteExecutorPreflightResult.model_validate(preflight),
            handoff=LiveRemoteCredentialHandoffResult.model_validate(handoff),
            credential_injection=LiveCredentialInjectionResult.model_validate(credential_injection),
            provider_envelope=LiveProviderRequestResult.model_validate(provider_envelope),
            client=StaticProviderDirectAdapterClient(LiveProviderDirectAdapterReceipt.model_validate(client_receipt)),
            execution_ref=execution_ref,
        ).to_payload()

    def live_gateway_external_transport(
        self,
        policy: dict[str, Any],
        preflight: dict[str, Any],
        gateway_envelope: dict[str, Any],
        client_result: dict[str, Any],
        *,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveGatewayExternalTransportRuntime().execute(
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            preflight=LiveRemoteExecutorPreflightResult.model_validate(preflight),
            gateway_envelope=LiveGatewayDeliveryResult.model_validate(gateway_envelope),
            client_result=LiveGatewayExternalClientResult.model_validate(client_result),
            execution_ref=execution_ref,
        ).to_payload()

    def live_gateway_owned_client_transport(
        self,
        policy: dict[str, Any],
        preflight: dict[str, Any],
        handoff: dict[str, Any],
        gateway_envelope: dict[str, Any],
        client_receipt: dict[str, Any],
        *,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveGatewayOwnedClientTransportRuntime().execute(
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            preflight=LiveRemoteExecutorPreflightResult.model_validate(preflight),
            handoff=LiveRemoteCredentialHandoffResult.model_validate(handoff),
            gateway_envelope=LiveGatewayDeliveryResult.model_validate(gateway_envelope),
            client=StaticGatewayOwnedClient(LiveGatewayOwnedClientReceipt.model_validate(client_receipt)),
            execution_ref=execution_ref,
        ).to_payload()

    def live_gateway_delivery_adapter(
        self,
        claim: dict[str, Any],
        policy: dict[str, Any],
        preflight: dict[str, Any],
        handoff: dict[str, Any],
        credential_injection: dict[str, Any],
        gateway_envelope: dict[str, Any],
        client_receipt: dict[str, Any],
        *,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveGatewayDeliveryAdapterRuntime().execute(
            claim=LiveProductionClaimResult.model_validate(claim),
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            preflight=LiveRemoteExecutorPreflightResult.model_validate(preflight),
            handoff=LiveRemoteCredentialHandoffResult.model_validate(handoff),
            credential_injection=LiveCredentialInjectionResult.model_validate(credential_injection),
            gateway_envelope=LiveGatewayDeliveryResult.model_validate(gateway_envelope),
            client=StaticGatewayDeliveryAdapterClient(LiveGatewayDeliveryAdapterReceipt.model_validate(client_receipt)),
            execution_ref=execution_ref,
        ).to_payload()

    def live_mcp_external_transport(
        self,
        policy: dict[str, Any],
        preflight: dict[str, Any],
        mcp_envelope: dict[str, Any],
        client_result: dict[str, Any],
        *,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveMcpExternalTransportRuntime().execute(
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            preflight=LiveRemoteExecutorPreflightResult.model_validate(preflight),
            mcp_envelope=LiveMcpRequestResult.model_validate(mcp_envelope),
            client_result=LiveMcpExternalClientResult.model_validate(client_result),
            execution_ref=execution_ref,
        ).to_payload()

    def live_mcp_owned_client_transport(
        self,
        policy: dict[str, Any],
        preflight: dict[str, Any],
        handoff: dict[str, Any],
        mcp_envelope: dict[str, Any],
        client_receipt: dict[str, Any],
        *,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveMcpOwnedClientTransportRuntime().execute(
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            preflight=LiveRemoteExecutorPreflightResult.model_validate(preflight),
            handoff=LiveRemoteCredentialHandoffResult.model_validate(handoff),
            mcp_envelope=LiveMcpRequestResult.model_validate(mcp_envelope),
            client=StaticMcpOwnedClient(LiveMcpOwnedClientReceipt.model_validate(client_receipt)),
            execution_ref=execution_ref,
        ).to_payload()

    def live_mcp_remote_adapter(
        self,
        claim: dict[str, Any],
        policy: dict[str, Any],
        preflight: dict[str, Any],
        handoff: dict[str, Any],
        credential_injection: dict[str, Any],
        mcp_envelope: dict[str, Any],
        client_receipt: dict[str, Any],
        *,
        execution_ref: str,
    ) -> dict[str, Any]:
        return LiveMcpRemoteAdapterRuntime().execute(
            claim=LiveProductionClaimResult.model_validate(claim),
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            preflight=LiveRemoteExecutorPreflightResult.model_validate(preflight),
            handoff=LiveRemoteCredentialHandoffResult.model_validate(handoff),
            credential_injection=LiveCredentialInjectionResult.model_validate(credential_injection),
            mcp_envelope=LiveMcpRequestResult.model_validate(mcp_envelope),
            client=StaticMcpRemoteAdapterClient(LiveMcpRemoteAdapterReceipt.model_validate(client_receipt)),
            execution_ref=execution_ref,
        ).to_payload()

    def live_transport_teardown_record(
        self,
        *,
        adapter_kind: str,
        policy: dict[str, Any],
        preflight: dict[str, Any],
        execution: dict[str, Any],
        audit: dict[str, Any],
        teardown_ref: str,
    ) -> dict[str, Any]:
        return LiveTransportTeardownRuntime().record(
            home=self.home,
            adapter_kind=adapter_kind,
            policy=LiveRemoteTransportPolicyResult.model_validate(policy),
            preflight=LiveRemoteExecutorPreflightResult.model_validate(preflight),
            execution=_transport_execution(adapter_kind=adapter_kind, payload=execution),
            audit=LiveTransportAuditResult.model_validate(audit),
            teardown_ref=teardown_ref,
        ).to_payload()

    def live_production_approval(
        self,
        *,
        adapter_kind: str,
        execution: dict[str, Any],
        audit: dict[str, Any],
        teardown: dict[str, Any],
        approval_receipt: dict[str, Any],
        operator_proof: dict[str, Any],
        production_ref: str,
    ) -> dict[str, Any]:
        parsed_execution = _transport_execution(adapter_kind=adapter_kind, payload=execution)
        if parsed_execution is None:
            raise ValueError("unsupported_adapter_kind")
        return LiveProductionApprovalRuntime().approve(
            adapter_kind=adapter_kind,
            execution=parsed_execution,
            audit=LiveTransportAuditResult.model_validate(audit),
            teardown=LiveTransportTeardownResult.model_validate(teardown),
            approval_receipt=ApprovalReceiptResult.model_validate_json(json.dumps(approval_receipt)),
            operator_proof=LiveOperatorProofResult.model_validate(operator_proof),
            production_ref=production_ref,
        ).to_payload()

    def live_production_claim(
        self,
        *,
        approval: dict[str, Any],
        claim_ref: str,
    ) -> dict[str, Any]:
        return LiveProductionClaimRuntime().record(
            home=self.home,
            approval=LiveProductionApprovalResult.model_validate(approval),
            claim_ref=claim_ref,
        ).to_payload()

    def live_operator_proof(
        self,
        *,
        proof_id: str,
        operator_id: str,
        handoff_manifest_id: Optional[str] = None,
        execution_plan_id: Optional[str] = None,
        proof_ref: Optional[str] = None,
        reviewed_risks: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        return LiveOperatorProofRuntime().record(
            proof_id=proof_id,
            operator_id=operator_id,
            handoff_manifest_id=handoff_manifest_id,
            execution_plan_id=execution_plan_id,
            proof_ref=proof_ref,
            reviewed_risks=reviewed_risks,
        ).to_payload()

    def live_profile(
        self,
        *,
        surface_id: str,
        principal_id: str,
        objective_id: str,
        delivery_target: Optional[str] = None,
        allowlisted_delivery_targets: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        return LiveProfileRuntime(home=self.home).build(
            surface_id=surface_id,
            principal_id=principal_id,
            objective_id=objective_id,
            delivery_target=delivery_target,
            allowlisted_delivery_targets=allowlisted_delivery_targets,
        ).to_payload()

    def live_dry_run(
        self,
        *,
        surface_id: str,
        principal_id: str,
        objective_id: str,
        delivery_target: Optional[str] = None,
        allowlisted_delivery_targets: tuple[str, ...] = (),
        execute_live: bool = False,
        check_credentials: bool = False,
        now: Optional[datetime] = None,
    ) -> dict[str, Any]:
        return LiveDryRunRuntime(home=self.home).run(
            surface_id=surface_id,
            principal_id=principal_id,
            objective_id=objective_id,
            delivery_target=delivery_target,
            allowlisted_delivery_targets=allowlisted_delivery_targets,
            execute_live=execute_live,
            check_credentials=check_credentials,
            now=now,
        ).to_payload()

    def live_readiness(self) -> dict[str, Any]:
        return LiveReadinessRuntime().build_report().to_payload()

    def live_optin_smoke(self) -> dict[str, Any]:
        return run_live_optin_smoke().to_payload()

    def live_beta_candidate(
        self,
        *,
        include_smoke: bool = False,
        scenario: str = "happy",
        operator_note: Optional[str] = None,
    ) -> dict[str, Any]:
        return build_live_beta_candidate_contract(
            include_smoke=include_smoke,
            scenario=scenario,
            operator_note=operator_note,
        ).to_payload()

    def production_foundation(
        self,
        *,
        include_credentials: bool = False,
        operator_note: Optional[str] = None,
    ) -> dict[str, Any]:
        return build_production_foundation_contract(
            home=self.home,
            include_credentials=include_credentials,
            operator_note=operator_note,
        ).to_payload()

    def provider_live_api(
        self,
        *,
        scenario: str = "status",
        secret_ref: str = "env://ZEUS_RC2_PROVIDER_KEY",
        message: str = "summarize provider live api checkpoint",
    ) -> dict[str, Any]:
        return build_provider_live_api_contract(
            scenario=scenario,
            secret_ref=secret_ref,
            message=message,
        ).to_payload()

    def mcp_live_server(
        self,
        *,
        scenario: str = "status",
        secret_ref: str = "env://ZEUS_RC3_MCP_TOKEN",
        query: str = "Zeus MCP live server checkpoint",
    ) -> dict[str, Any]:
        return build_mcp_live_server_contract(
            scenario=scenario,
            secret_ref=secret_ref,
            query=query,
        ).to_payload()

    def gateway_live_delivery(
        self,
        *,
        scenario: str = "status",
        secret_ref: str = "env://ZEUS_RC4_GATEWAY_TOKEN",
        target: str = "slack://ops",
        message: str = "Zeus gateway live delivery checkpoint",
    ) -> dict[str, Any]:
        return build_gateway_live_delivery_contract(
            scenario=scenario,
            secret_ref=secret_ref,
            target=target,
            message=message,
            home=self.home,
        ).to_payload()

    def sandbox_terminal_live(
        self,
        *,
        scenario: str = "status",
        command: str = "pwd",
        home: Optional[Path] = None,
    ) -> dict[str, Any]:
        return build_sandbox_terminal_live_contract(
            scenario=scenario,
            command=command,
            home=home or self.home,
        ).to_payload()

    def memory_privacy_live(
        self,
        *,
        scenario: str = "status",
        home: Optional[Path] = None,
    ) -> dict[str, Any]:
        return build_memory_privacy_live_contract(
            scenario=scenario,
            home=home or self.home,
        ).to_payload()

    def provider_live_optin(
        self,
        *,
        scenario: str = "status",
        endpoint: str = "https://api.openai.local/v1/chat/completions",
        allowed_host: str = "api.openai.local",
        secret_ref: str = "env://ZEUS_RC7_PROVIDER_KEY",
        model_id: str = "gpt-rc7-external",
        message: str = "summarize provider live opt-in checkpoint",
    ) -> dict[str, Any]:
        return build_provider_live_optin_contract(
            scenario=scenario,
            endpoint=endpoint,
            allowed_host=allowed_host,
            secret_ref=secret_ref,
            model_id=model_id,
            message=message,
        ).to_payload()

    def provider_owned_client_live(
        self,
        *,
        scenario: str = "status",
        endpoint: str = "https://api.openai.local/v1/chat/completions",
        allowed_host: str = "api.openai.local",
        secret_ref: str = "env://ZEUS_RC8_PROVIDER_KEY",
        model_id: str = "gpt-rc8-owned-client",
        message: str = "summarize provider owned client live checkpoint",
    ) -> dict[str, Any]:
        return build_provider_owned_client_live_contract(
            scenario=scenario,
            endpoint=endpoint,
            allowed_host=allowed_host,
            secret_ref=secret_ref,
            model_id=model_id,
            message=message,
        ).to_payload()

    def mcp_owned_client_live(
        self,
        *,
        scenario: str = "status",
        endpoint: str = "https://mcp.github.local/rpc",
        allowed_host: str = "mcp.github.local",
        secret_ref: str = "env://ZEUS_RC9_MCP_TOKEN",
        server_id: str = "mcp.github",
        tool_name: str = "repo.search",
        query: str = "Zeus MCP owned client live checkpoint",
    ) -> dict[str, Any]:
        return build_mcp_owned_client_live_contract(
            scenario=scenario,
            endpoint=endpoint,
            allowed_host=allowed_host,
            secret_ref=secret_ref,
            server_id=server_id,
            tool_name=tool_name,
            query=query,
        ).to_payload()

    def mcp_status(self, *, server_id: Optional[str] = None) -> dict[str, Any]:
        return McpCockpitRuntime().build(server_id=server_id).to_payload()

    def mcp_add(self, *, server_ref: str) -> dict[str, Any]:
        return McpSettingsRuntime(self.home).add(server_ref=server_ref).to_payload()

    def mcp_config(self) -> dict[str, Any]:
        return McpSettingsRuntime(self.home).list().to_payload()

    def model_status(self, *, provider_id: Optional[str] = None) -> dict[str, Any]:
        return ModelCockpitRuntime().build(provider_id=provider_id).to_payload()

    def remember_status(self, *, subject: Optional[str] = None) -> dict[str, Any]:
        return MemoryCockpitRuntime(self.home).build(subject=subject).to_payload()

    def remember_add(
        self,
        *,
        subject: str,
        predicate: str,
        object_text: str,
        provenance_id: str,
    ) -> dict[str, Any]:
        return MemoryEntryRuntime(self.home).add(
            subject=subject,
            predicate=predicate,
            object_text=object_text,
            provenance_id=provenance_id,
        ).to_payload()

    def gateway_status(self, *, adapter_id: Optional[str] = None) -> dict[str, Any]:
        return GatewayCockpitRuntime().build(adapter_id=adapter_id).to_payload()

    def gateway_add(self, *, adapter_ref: str, target: str) -> dict[str, Any]:
        return GatewaySettingsRuntime(self.home).add(adapter_ref=adapter_ref, target=target).to_payload()

    def gateway_config(self) -> dict[str, Any]:
        return GatewaySettingsRuntime(self.home).list().to_payload()

    def gateway_pair(self, *, adapter_id: str, target: str, proof_ref: str) -> dict[str, Any]:
        return GatewayPairingRuntime(self.home).pair(
            adapter_id=adapter_id,
            target=target,
            proof_ref=proof_ref,
        ).to_payload()

    def gateway_pairings(self) -> dict[str, Any]:
        return GatewayPairingRuntime(self.home).list().to_payload()

    def tool_status(self, *, tool_id: Optional[str] = None) -> dict[str, Any]:
        return ToolCockpitRuntime().build(tool_id=tool_id).to_payload()

    def runtime_status(self, *, backend_id: Optional[str] = None) -> dict[str, Any]:
        return RuntimeCockpitRuntime().build(backend_id=backend_id, root=self.home).to_payload()

    def workflow_status(self, *, workflow_id: Optional[str] = None) -> dict[str, Any]:
        return WorkflowCockpitRuntime().build(workflow_id=workflow_id).to_payload()

    def security_status(
        self,
        *,
        control_id: Optional[str] = None,
        include_credentials: bool = False,
    ) -> dict[str, Any]:
        return SecurityCockpitRuntime(home=self.home).build(
            control_id=control_id,
            include_credentials=include_credentials,
        ).to_payload()

    def credential_readiness(self) -> dict[str, Any]:
        return CredentialReadinessRuntime(self.home).build().to_payload()

    def credential_bind(
        self,
        *,
        surface_kind: str,
        surface_id: str,
        credential_scope: str,
        env_ref: Optional[str] = None,
        vault_ref: Optional[str] = None,
    ) -> dict[str, Any]:
        return CredentialReadinessRuntime(self.home).bind(
            surface_kind=surface_kind,
            surface_id=surface_id,
            credential_scope=credential_scope,
            env_ref=env_ref,
            vault_ref=vault_ref,
        ).to_payload()

    def secret_resolver_plan(
        self,
        *,
        surface_kind: str,
        surface_id: str,
        credential_scope: Optional[str],
        expected_endpoint: Optional[str] = None,
    ) -> dict[str, Any]:
        return SecretResolverPlanRuntime(self.home).plan(
            surface_kind=surface_kind,
            surface_id=surface_id,
            credential_scope=credential_scope,
            expected_endpoint=expected_endpoint,
        ).to_payload()

    def approval_status(self, *, approval_id: Optional[str] = None) -> dict[str, Any]:
        return ApprovalCockpitRuntime().build(approval_id=approval_id).to_payload()

    def approval_receipt_status(
        self,
        *,
        approval_id: str,
        principal_id: str,
        objective_id: str,
        capability_id: str,
    ) -> dict[str, Any]:
        return ApprovalReceiptRuntime().record(
            approval_id=approval_id,
            principal_id=principal_id,
            objective_id=objective_id,
            capability_id=capability_id,
        ).to_payload()

    def catalogs(self) -> dict[str, Any]:
        providers = provider_catalog_payload()
        tools = native_tool_catalog_payload()
        mcp = curated_mcp_catalog_payload()
        return {
            "provider_count": providers["provider_profile_count"],
            "api_modes": providers["api_modes"],
            "toolset_count": tools["toolset_count"],
            "tool_count": tools["tool_count"],
            "mcp_catalog_entry_count": mcp["catalog_entry_count"],
            "mcp_beta_enabled_count": mcp["beta_enabled_count"],
            "network_opened": False,
            "live_production_claimed": False,
        }


def _adapter_plan(*, adapter_kind: str, payload: dict[str, Any]):
    if adapter_kind == "provider":
        return LiveProviderAdapterResult.model_validate(payload)
    if adapter_kind == "gateway":
        return LiveGatewayAdapterResult.model_validate(payload)
    return LiveMcpAdapterResult.model_validate(payload)


def _transport_execution(*, adapter_kind: str, payload: Optional[dict[str, Any]]):
    if payload is None:
        return None
    if adapter_kind == "provider":
        if payload.get("provider_direct_adapter") is True:
            return LiveProviderDirectAdapterResult.model_validate(payload)
        if payload.get("provider_owned_client") is True:
            return LiveProviderOwnedClientTransportResult.model_validate(payload)
        if payload.get("transport_kind") == "external_http":
            return LiveProviderExternalTransportResult.model_validate(payload)
        if payload.get("transport_kind") == "local_http":
            return LiveProviderHttpTransportResult.model_validate(payload)
        return LiveProviderLoopbackTransportResult.model_validate(payload)
    if adapter_kind == "gateway":
        if payload.get("gateway_delivery_adapter") is True:
            return LiveGatewayDeliveryAdapterResult.model_validate(payload)
        if payload.get("gateway_owned_client") is True:
            return LiveGatewayOwnedClientTransportResult.model_validate(payload)
        if payload.get("transport_kind") == "external_http":
            return LiveGatewayExternalTransportResult.model_validate(payload)
        if payload.get("transport_kind") == "local_http":
            return LiveGatewayHttpTransportResult.model_validate(payload)
        return LiveGatewayLoopbackTransportResult.model_validate(payload)
    if adapter_kind == "mcp":
        if payload.get("mcp_remote_adapter") is True:
            return LiveMcpRemoteAdapterResult.model_validate(payload)
        if payload.get("mcp_owned_client") is True:
            return LiveMcpOwnedClientTransportResult.model_validate(payload)
        if payload.get("transport_kind") == "remote_server":
            return LiveMcpExternalTransportResult.model_validate(payload)
        if payload.get("transport_kind") == "local_http":
            return LiveMcpHttpTransportResult.model_validate(payload)
        return LiveMcpLoopbackTransportResult.model_validate(payload)
    return None


__all__ = ["ZeusAgent"]
