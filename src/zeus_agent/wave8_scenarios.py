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
from zeus_agent.kernel.authority import (
    AuthorityContext,
    CapabilityGrant,
    CredentialGrant,
    NetworkGrant,
)
from zeus_agent.kernel.capabilities import CapabilityDescriptor, CapabilityRisk
from zeus_agent.kernel.evidence import EvidenceStatus, MnemeEvidenceRecord
from zeus_agent.model_runtime.execution import (
    ProviderExecutionRequest,
    ProviderExecutionRuntime,
)
from zeus_agent.state import SQLiteTransportRuntimeStateStore
from zeus_agent.transport_runtime import (
    TransportExecutionGate,
    TransportExecutionGateRequest,
    TransportKind,
    TransportRegistry,
    default_wave8_manifests,
    default_wave8_probes,
)

RUN_ID = "wave8-run"
GOAL_CONTRACT_ID = "wave8-goal"


def wave8_transport_state_payload(home: Path) -> dict[str, object]:
    store = SQLiteTransportRuntimeStateStore(home / "wave8-transport.sqlite3")
    first = _persist_transport_state(store)
    second = _persist_transport_state(store)
    counts = store.transport_counts().model_dump(mode="json")
    payload = {
        "fake_local_only": True,
        "no_external_side_effects": True,
        "live_transport": False,
        "state_db": str(store.db_path),
        "transport_counts": counts,
        "transport_manifest_count": counts["transport_manifests"],
        "transport_probe_count": counts["transport_probe_receipts"],
        "evidence_link_count": counts["transport_evidence_links"],
        "idempotency_replay_stable": first == second == counts,
        "manifests": _probed_registry().manifest_report(),
        "health": _probed_registry().health_report(),
        "transport_ids": _probed_registry().summary().transport_ids,
    }
    return payload | {"no_secret_echo": _no_secret_echo(payload)}


def wave8_runtime_integration_payload(*, raw_secret: str) -> dict[str, object]:
    registry = _probed_registry()
    gate = TransportExecutionGate(registry)
    provider = ProviderExecutionRuntime(transport_registry=registry).prepare(
        ProviderExecutionRequest(
            provider="external",
            prompt="draft a registry-bound plan",
            required_json_mode=True,
            network_host="api.openai.local",
            credential_scope="external.openai.readonly",
        ),
        _authority(
            ["provider.external.generate"],
            network_hosts=[("provider.external.generate", "api.openai.local")],
            credential_scopes=[
                ("provider.external.generate", "external.openai.readonly"),
            ],
        ),
    )
    mcp = ConnectorExecutionRuntime(
        _connector_registry(),
        transport_registry=registry,
    ).execute(ConnectorExecutionRequest(capability_id="mcp.echo"), _authority(["mcp.echo"]))
    api = ConnectorExecutionRuntime(
        _connector_registry(),
        transport_registry=registry,
    ).execute(
        ConnectorExecutionRequest(
            capability_id="api.fetch",
            credential_scope="external.partner.readonly",
        ),
        _authority(
            ["api.fetch"],
            credential_scopes=[("api.fetch", "external.partner.readonly")],
        ),
    )
    unknown = gate.evaluate(
        TransportExecutionGateRequest(
            capability_id="provider.missing.generate",
            transport_kind=TransportKind.provider,
        ),
        _authority(["provider.missing.generate"]),
    )
    mismatch = gate.evaluate(
        TransportExecutionGateRequest(
            capability_id="provider.external.generate",
            transport_kind=TransportKind.api,
        ),
        _authority(["provider.external.generate"]),
    )
    live = gate.evaluate(
        TransportExecutionGateRequest(
            capability_id="provider.external.generate",
            transport_kind=TransportKind.provider,
            live_transport=True,
        ),
        _authority(
            ["provider.external.generate"],
            network_hosts=[("provider.external.generate", "api.openai.local")],
            credential_scopes=[
                ("provider.external.generate", "external.openai.readonly"),
            ],
        ),
    )
    secret = gate.evaluate(
        TransportExecutionGateRequest(
            capability_id="api.fetch",
            transport_kind=TransportKind.api,
            credential_scope=raw_secret,
        ),
        _authority(["api.fetch"]),
    )
    payload = {
        "fake_local_only": True,
        "registry_gate": "enabled",
        "healthy_provider_allowed": provider.decision == "selected",
        "healthy_connector_allowed": mcp.decision == "allowed",
        "unknown_transport": _block_label(unknown.decision),
        "unhealthy_probe": _block_label(api.decision),
        "transport_kind_mismatch": _block_label(mismatch.decision),
        "live_transport_not_authorized": _block_label(live.decision),
        "secret_like_credential_scope": "redacted" if secret.redacted_input else secret.reason,
        "blocked_handler_executed": api.handler_executed,
        "network_opened": False,
        "provider": provider.model_dump(mode="json"),
        "connector": mcp.model_dump(mode="json"),
    }
    return payload | {"no_secret_echo": raw_secret not in json.dumps(payload, sort_keys=True)}


def _persist_transport_state(store: SQLiteTransportRuntimeStateStore) -> dict[str, int]:
    registry = _probed_registry()
    for manifest in registry.manifest_report():
        transport_id = str(manifest["transport_id"])
        evidence_id = "evidence-wave8-manifest-{0}".format(transport_id)
        store.add_evidence(evidence_id, _evidence("REQ-ZEUS-WAVE8-001:S1", transport_id))
        store.add_transport_manifest(
            manifest_id="transport-manifest-{0}".format(transport_id),
            manifest=manifest,
            evidence_id=evidence_id,
            idempotency_key="idem-wave8-manifest-{0}".format(transport_id),
        )
    for receipt in registry.probe_report():
        probe_id = str(receipt["probe_id"])
        transport_id = str(receipt["transport_id"])
        evidence_id = "evidence-wave8-probe-{0}".format(probe_id)
        store.add_evidence(evidence_id, _evidence("REQ-ZEUS-WAVE8-001:S1", transport_id))
        store.add_transport_probe_receipt(
            probe_receipt_id="transport-probe-{0}".format(probe_id),
            receipt=receipt,
            evidence_id=evidence_id,
            idempotency_key="idem-wave8-probe-{0}".format(probe_id),
        )
        store.add_transport_health(
            transport_id=transport_id,
            health=str(receipt["health"]),
            evidence_id=evidence_id,
            idempotency_key="idem-wave8-health-{0}".format(transport_id),
        )
    return store.transport_counts().model_dump(mode="json")


def _probed_registry() -> TransportRegistry:
    registry = TransportRegistry()
    for manifest in default_wave8_manifests():
        registry.register(manifest)
    for probe in default_wave8_probes():
        registry.run_probe(probe)
    return registry


def _evidence(criterion_id: str, capability_id: str) -> MnemeEvidenceRecord:
    return MnemeEvidenceRecord(
        run_id=RUN_ID,
        goal_contract_id=GOAL_CONTRACT_ID,
        criterion_id=criterion_id,
        evidence_type="transport_state",
        summary="wave8 transport state persisted",
        status=EvidenceStatus.PASS,
        capability_id=capability_id,
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
    registry.register(
        ConnectorDeclaration(
            connector_id="api-conn",
            kind=ConnectorKind.api,
            display_name="Partner API",
            descriptors=[_descriptor("api.fetch")],
        )
    )
    registry.set_state("mcp-conn", ConnectorLifecycleState.healthy)
    registry.set_state("api-conn", ConnectorLifecycleState.healthy)
    return registry


def _descriptor(capability_id: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        name=capability_id,
        risk=CapabilityRisk.low,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
    )


def _authority(
    capability_ids: list[str],
    *,
    network_hosts: list[tuple[str, str]] | None = None,
    credential_scopes: list[tuple[str, str]] | None = None,
) -> AuthorityContext:
    return AuthorityContext(
        principal_id="wave8-principal",
        run_id=RUN_ID,
        goal_contract_id=GOAL_CONTRACT_ID,
        capability_grants=[
            CapabilityGrant(capability_id=capability_id)
            for capability_id in capability_ids
        ],
        network_grants=[
            NetworkGrant(capability_id=capability_id, network_host=network_host)
            for capability_id, network_host in network_hosts or []
        ],
        credential_grants=[
            CredentialGrant(capability_id=capability_id, credential_scope=credential_scope)
            for capability_id, credential_scope in credential_scopes or []
        ],
    )


def _block_label(decision: str) -> str:
    return "blocked" if decision == "blocked" else decision


def _no_secret_echo(payload: dict[str, object]) -> bool:
    serialized = json.dumps(payload, sort_keys=True)
    return (
        "ghp_TEST_FIXTURE" not in serialized
        and "OPENAI_API_KEY" not in serialized
        and "sk-" not in serialized
    )
