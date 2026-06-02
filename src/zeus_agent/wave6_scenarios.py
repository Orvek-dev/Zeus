from __future__ import annotations

import json
from pathlib import Path

from zeus_agent.connector_runtime import (
    ConnectorDeclaration,
    ConnectorExecutionRequest,
    ConnectorExecutionRuntime,
    ConnectorKind,
    ConnectorLifecycleRegistry,
    ConnectorLifecycleState,
)
from zeus_agent.kernel.authority import AuthorityContext, CapabilityGrant
from zeus_agent.kernel.capabilities import CapabilityDescriptor, CapabilityRisk
from zeus_agent.kernel.evidence import EvidenceStatus, MnemeEvidenceRecord
from zeus_agent.model_runtime.execution import (
    ProviderExecutionRequest,
    ProviderExecutionRuntime,
)
from zeus_agent.runtime_promotion import (
    LiveTransportPromotionGuard,
    LiveTransportPromotionRequest,
    RollbackPlan,
)
from zeus_agent.state import SQLiteRuntimeStateStore
from zeus_agent.workflow_runtime.jobs import RetryPolicy

RUN_ID = "wave6-run"
GOAL_CONTRACT_ID = "wave6-goal"


def wave6_runtime_state_payload(home: Path) -> dict[str, object]:
    store = SQLiteRuntimeStateStore(home / "wave6-state.sqlite3")
    provider = ProviderExecutionRuntime().prepare(
        ProviderExecutionRequest(
            provider="local",
            prompt="persist local runtime state",
            local_private=True,
            required_json_mode=True,
        ),
        _authority(["provider.local.generate"]),
    )
    registry = _connector_registry()
    registry.set_state("mcp-conn", ConnectorLifecycleState.healthy)
    connector = ConnectorExecutionRuntime(registry).execute(
        ConnectorExecutionRequest(capability_id="mcp.echo"),
        _authority(["mcp.echo"]),
    )
    _persist_provider(store, provider.model_dump(mode="json"))
    _persist_connector(store, connector.model_dump(mode="json"))
    runtime_counts = store.runtime_counts().model_dump(mode="json")
    payload = {
        "fake_local_only": True,
        "no_external_side_effects": True,
        "live_transport": False,
        "state_db": str(store.db_path),
        "runtime_counts": runtime_counts,
        "provider_execution_count": runtime_counts["provider_executions"],
        "connector_execution_count": runtime_counts["connector_executions"],
        "evidence_link_count": runtime_counts["execution_evidence_links"],
        "provider_execution": {
            "execution_id": "provider-exec-wave6-001",
            "idempotency_key": "idem-wave6-provider-001",
            "envelope": provider.envelope.model_dump(mode="json") if provider.envelope else None,
        },
        "connector_execution": {
            "execution_id": "connector-exec-wave6-001",
            "idempotency_key": "idem-wave6-connector-001",
            "envelope": connector.envelope.model_dump(mode="json") if connector.envelope else None,
            "broker_decision": connector.decision,
            "handler_executed": connector.handler_executed,
        },
    }
    return payload | {"no_secret_echo": _no_secret_echo(payload)}


def wave6_promotion_controls_payload(home: Path) -> dict[str, object]:
    store = SQLiteRuntimeStateStore(home / "wave6-promotion.sqlite3")
    request = LiveTransportPromotionRequest(
        promotion_id="promotion-wave6-001",
        capability_id="provider.external.generate",
        transport_kind="provider",
        idempotency_key="idem-wave6-promotion-001",
        credential_scope="external.openai.readonly",
        network_host="api.openai.local",
        retry_policy=RetryPolicy(max_attempts=3, backoff_seconds=5),
        rollback_plan=RollbackPlan(
            command="disable-live-transport",
            target="provider.external.generate",
        ),
    )
    promotion = LiveTransportPromotionGuard().evaluate(request)
    store.add_transport_promotion(
        promotion_id=promotion.promotion_id,
        capability_id=promotion.capability_id,
        transport_kind=promotion.transport_kind,
        decision=promotion.decision,
        reason=promotion.reason,
        approval_required=promotion.approval_required,
        handler_executed=promotion.handler_executed,
        network_opened=promotion.network_opened,
        retry_policy=promotion.retry_policy,
        rollback_plan=promotion.rollback_plan,
        idempotency_key=promotion.idempotency_key,
    )
    payload = {
        "fake_local_only": True,
        "no_external_side_effects": True,
        "state_db": str(store.db_path),
        "runtime_counts": store.runtime_counts().model_dump(mode="json"),
        "promotion": promotion.model_dump(mode="json"),
    }
    return payload | {"no_secret_echo": _no_secret_echo(payload)}


def _persist_provider(store: SQLiteRuntimeStateStore, result: dict[str, object]) -> None:
    envelope = result["envelope"]
    if not isinstance(envelope, dict):
        raise ValueError("provider envelope missing")
    evidence_id = "evidence-wave6-provider-001"
    store.add_evidence(
        evidence_id,
        _evidence(
            criterion_id="REQ-ZEUS-WAVE6-001:S1",
            evidence_type="provider_execution",
            summary="provider_execution persisted",
            capability_id="provider.local.generate",
        ),
    )
    store.add_provider_execution(
        provider_execution_id="provider-exec-wave6-001",
        run_id=RUN_ID,
        goal_contract_id=GOAL_CONTRACT_ID,
        provider=str(envelope["provider"]),
        provider_id=str(envelope["provider_id"]),
        model_id=str(envelope["model_id"]),
        envelope=envelope,
        broker_decision=str(result["decision"]),
        evidence_id=evidence_id,
        idempotency_key="idem-wave6-provider-001",
        live_transport=False,
    )
    store.add_execution_evidence_link(
        execution_kind="provider",
        execution_id="provider-exec-wave6-001",
        evidence_id=evidence_id,
    )


def _persist_connector(store: SQLiteRuntimeStateStore, result: dict[str, object]) -> None:
    envelope = result["envelope"]
    if not isinstance(envelope, dict):
        raise ValueError("connector envelope missing")
    evidence_id = "evidence-wave6-connector-001"
    store.add_evidence(
        evidence_id,
        _evidence(
            criterion_id="REQ-ZEUS-WAVE6-002:S1",
            evidence_type="connector_execution",
            summary="connector_execution persisted",
            capability_id=str(envelope["capability_id"]),
        ),
    )
    store.add_connector_execution(
        connector_execution_id="connector-exec-wave6-001",
        run_id=RUN_ID,
        goal_contract_id=GOAL_CONTRACT_ID,
        connector_id=str(envelope["connector_id"]),
        connector_kind=str(envelope["connector_kind"]),
        capability_id=str(envelope["capability_id"]),
        envelope=envelope,
        broker_decision=str(result["decision"]),
        handler_executed=bool(result["handler_executed"]),
        evidence_id=evidence_id,
        idempotency_key="idem-wave6-connector-001",
        live_transport=False,
    )
    store.add_execution_evidence_link(
        execution_kind="connector",
        execution_id="connector-exec-wave6-001",
        evidence_id=evidence_id,
    )


def _evidence(
    *,
    criterion_id: str,
    evidence_type: str,
    summary: str,
    capability_id: str,
) -> MnemeEvidenceRecord:
    return MnemeEvidenceRecord(
        run_id=RUN_ID,
        goal_contract_id=GOAL_CONTRACT_ID,
        criterion_id=criterion_id,
        evidence_type=evidence_type,
        summary=summary,
        status=EvidenceStatus.PASS,
        capability_id=capability_id,
    )


def _authority(capability_ids: list[str]) -> AuthorityContext:
    return AuthorityContext(
        principal_id="wave6-principal",
        run_id=RUN_ID,
        goal_contract_id=GOAL_CONTRACT_ID,
        capability_grants=[CapabilityGrant(capability_id=value) for value in capability_ids],
    )


def _connector_registry() -> ConnectorLifecycleRegistry:
    registry = ConnectorLifecycleRegistry()
    registry.register(
        ConnectorDeclaration(
            connector_id="mcp-conn",
            kind=ConnectorKind.mcp,
            display_name="Local MCP",
            descriptors=[_descriptor("mcp.echo")],
        )
    )
    return registry


def _descriptor(capability_id: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        name=capability_id,
        risk=CapabilityRisk.low,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
    )


def _no_secret_echo(payload: dict[str, object]) -> bool:
    encoded = json.dumps(payload, sort_keys=True)
    return (
        "ghp_TEST_FIXTURE" not in encoded
        and "OPENAI_API_KEY" not in encoded
        and "sk-" not in encoded
    )
