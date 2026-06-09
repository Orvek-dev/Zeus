from __future__ import annotations

from collections.abc import Sequence

from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityRisk,
    EvidenceObligation,
    SideEffect,
)

from .models import LiveCapability


class LiveCapabilityRegistry:
    def __init__(self, capabilities: Sequence[LiveCapability]) -> None:
        self._capabilities = tuple(capabilities)
        self._by_id = {capability.capability_id: capability for capability in self._capabilities}

    def require(self, capability_id: str) -> LiveCapability:
        capability = self._by_id.get(capability_id)
        if capability is None:
            raise KeyError(capability_id)
        return capability

    def list_capabilities(self) -> tuple[LiveCapability, ...]:
        return self._capabilities

    def to_capability_graph(self) -> CapabilityGraph:
        descriptors = [
            CapabilityDescriptor(
                capability_id=capability.capability_id,
                name=capability.capability_id.replace(".", "_").replace("-", "_"),
                risk=CapabilityRisk.high,
                input_schema={
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string"},
                        "scenario": {"type": "string"},
                        "credential_scope": {"type": "string"},
                    },
                    "required": ["provider", "scenario"],
                },
                output_schema={
                    "type": "object",
                    "properties": {"status": {"type": "string"}},
                    "required": ["status"],
                },
                description="Governed live capability mediated by Zeus kernel broker.",
                side_effects=[SideEffect.network],
                evidence_obligation=EvidenceObligation.decision,
            )
            for capability in self._capabilities
        ]
        return CapabilityGraph(descriptors)


def default_live_capability_registry() -> LiveCapabilityRegistry:
    return LiveCapabilityRegistry(
        (
            LiveCapability(
                capability_id="provider.local-smoke",
                provider="provider",
                scenario="local-smoke",
                lease_ref="lease://v210/provider-local-smoke",
                approval_ref="approval://v210/provider-local-smoke",
                promotion_guard_ref="promotion-guard://v210/provider-local-smoke",
                broker_evidence_ref="broker-evidence://v210/provider-local-smoke",
                credential_scope="credential.local-smoke",
            ),
            _local_smoke_capability("mcp.local-smoke", "mcp"),
            _local_smoke_capability("gateway.loopback-smoke", "gateway"),
            _local_smoke_capability("local-sandbox.local-smoke", "local-sandbox"),
        ),
    )


def _local_smoke_capability(capability_id: str, provider: str) -> LiveCapability:
    return LiveCapability(
        capability_id=capability_id,
        provider=provider,
        scenario="local-smoke",
        lease_ref="lease://v580/{0}".format(capability_id),
        approval_ref="approval://v580/{0}".format(capability_id),
        promotion_guard_ref="promotion-guard://v580/{0}".format(capability_id),
        broker_evidence_ref="broker-evidence://v580/{0}".format(capability_id),
        credential_scope="credential.{0}".format(capability_id),
    )
