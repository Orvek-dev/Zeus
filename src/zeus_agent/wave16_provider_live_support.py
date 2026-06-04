from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Final

from zeus_agent.kernel.authority import ApprovalReceipt
from zeus_agent.model_runtime.interfaces import (
    ProviderMessage,
    ProviderMetadataEntry,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
)
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.wave16_provider_http_server import Wave16ProviderHttpServer

EVIDENCE_TARGET: Final = "mneme.wave16.provider_live"
ISSUED_AT: Final = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
EXPIRES_AT: Final = datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc)


def openai_url(server: Wave16ProviderHttpServer) -> str:
    return "{0}/v1/chat/completions".format(server.base_url)


def lease(network_hosts: tuple[str, ...]) -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave16.lease.provider.live",
        objective_id="wave16.objective.provider.live",
        principal_id="wave16.principal.provider",
        run_id="wave16.run.provider.live",
        allowed_capabilities=("provider.external.generate", "provider.local.generate"),
        credential_scopes=("external.openai.readonly",),
        network_hosts=network_hosts,
        budget_limit=10_000,
        evidence_target=EVIDENCE_TARGET,
        live_transport_allowed=True,
        issued_at=ISSUED_AT,
        expires_at=EXPIRES_AT,
    )


def openai_request(
    endpoint: str,
    network_host: str,
    *,
    approval: bool = True,
    timeout: bool = True,
    live_network: bool = True,
    credential_scope: str | None = "external.openai.readonly",
    approval_capability: str = "provider.external.generate",
    approval_receipt: str | None = None,
) -> ProviderRuntimeRequest:
    return ProviderRuntimeRequest(
        provider_kind="openai_compatible",
        provider_id="openai.wave16.loopback",
        model_id="gpt-wave16",
        messages=(ProviderMessage(role="user", content="Call the loopback provider."),),
        credential_scope=credential_scope,
        network_host=network_host,
        live_network=live_network,
        evidence_target=EVIDENCE_TARGET,
        metadata=metadata(
            endpoint,
            approval=approval,
            timeout=timeout,
            approval_capability=approval_capability,
            approval_receipt=approval_receipt,
        ),
    )


def local_request(endpoint: str, network_host: str) -> ProviderRuntimeRequest:
    return ProviderRuntimeRequest(
        provider_kind="local_llm",
        provider_id="local.wave16.loopback",
        model_id="qwen2.5-coder:7b",
        messages=(ProviderMessage(role="user", content="Use local loopback LLM."),),
        network_host=network_host,
        live_network=True,
        evidence_target=EVIDENCE_TARGET,
        metadata=(
            *metadata(
                endpoint,
                approval=True,
                timeout=True,
                approval_capability="provider.local.generate",
                approval_receipt=None,
            ),
            ProviderMetadataEntry(key="local.runtime_model", value="qwen2.5-coder:7b"),
        ),
    )


def metadata(
    endpoint: str,
    *,
    approval: bool,
    timeout: bool,
    approval_capability: str,
    approval_receipt: str | None,
) -> tuple[ProviderMetadataEntry, ...]:
    entries = [ProviderMetadataEntry(key="live.endpoint", value=endpoint)]
    if approval:
        entries.append(
            ProviderMetadataEntry(
                key="approval.receipt",
                value=approval_receipt or approval_receipt_json(approval_capability),
            ),
        )
    if timeout:
        entries.append(ProviderMetadataEntry(key="live.timeout_ms", value=2_000))
    return tuple(entries)


def approval_receipt_json(capability_id: str) -> str:
    return ApprovalReceipt(
        principal_id="wave16.principal.provider",
        run_id="wave16.run.provider.live",
        goal_contract_id="wave16.objective.provider.live",
        approved_capabilities=[capability_id],
    ).model_dump_json()


def block_label(response: ProviderRuntimeResponse, reason: str) -> str:
    if response.decision == "blocked" and response.metadata_value("block.reason") == reason:
        return "blocked"
    value = response.metadata_value("block.reason")
    return "missing_block_reason" if value is None else str(value)


def all_metadata_true(responses: tuple[ProviderRuntimeResponse, ...], key: str) -> bool:
    return all(response.metadata_value(key) is True for response in responses)


def all_have_metadata(responses: tuple[ProviderRuntimeResponse, ...], key: str) -> bool:
    return all(response.metadata_value(key) is not None for response in responses)


def no_secret_echo(responses: tuple[ProviderRuntimeResponse, ...]) -> bool:
    serialized = json.dumps(
        [response.model_dump(mode="json") for response in responses],
        sort_keys=True,
    )
    redacted_markers_removed = serialized.replace("sk-...redacted", "[redacted-secret]")
    return "sk-" not in redacted_markers_removed and "ghp_" not in redacted_markers_removed
