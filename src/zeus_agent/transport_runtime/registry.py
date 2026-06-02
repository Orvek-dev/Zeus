from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.kernel.authority import ApprovalReceipt, AuthorityContext
from zeus_agent.runtime_promotion import (
    LiveTransportPromotionGuard,
    LiveTransportPromotionRequest,
    LiveTransportPromotionResult,
)
from zeus_agent.transport_runtime.manifest import (
    TransportAdapterManifest,
    TransportHealth,
    TransportPolicyBlock,
)
from zeus_agent.transport_runtime.probes import ProbeReceipt, SandboxProbeDefinition


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class TransportRegistryError(ValueError):
    def __init__(self, reason: str, *, transport_id: Optional[str] = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.transport_id = transport_id


class TransportRegistrySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    transport_ids: tuple[str, ...]
    sandbox_probe_count: int
    live_transport: bool

    @field_validator("transport_ids")
    @classmethod
    def _validate_transport_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, "transport_ids") for value in values)


class TransportRegistry:
    def __init__(self) -> None:
        self._manifests: dict[str, TransportAdapterManifest] = {}
        self._health: dict[str, TransportHealth] = {}
        self._probe_receipts: list[ProbeReceipt] = []

    def register(self, manifest: TransportAdapterManifest) -> None:
        if manifest.transport_id in self._manifests:
            raise TransportRegistryError(
                "duplicate_transport_id",
                transport_id=manifest.transport_id,
            )
        if manifest.policy.live_transport:
            raise TransportRegistryError(
                "live_transport_not_authorized",
                transport_id=manifest.transport_id,
            )
        self._manifests[manifest.transport_id] = manifest
        self._health[manifest.transport_id] = TransportHealth.unknown

    def run_probe(self, probe: SandboxProbeDefinition) -> ProbeReceipt:
        if probe.transport_id not in self._manifests:
            raise TransportRegistryError(
                "unknown_transport_id",
                transport_id=probe.transport_id,
            )
        receipt = ProbeReceipt(
            probe_id=probe.probe_id,
            transport_id=probe.transport_id,
            health=probe.expected_health,
        )
        self._health[probe.transport_id] = probe.expected_health
        self._probe_receipts.append(receipt)
        return receipt

    def blocked_probe(self, probe: SandboxProbeDefinition) -> TransportPolicyBlock:
        if probe.transport_id not in self._manifests:
            return TransportPolicyBlock(
                reason="unknown_transport_id",
                transport_id=probe.transport_id,
            )
        return TransportPolicyBlock(reason="probe_not_blocked", transport_id=probe.transport_id)

    def evaluate_live_enablement(
        self,
        request: LiveTransportPromotionRequest,
        *,
        authority: Optional[AuthorityContext] = None,
        approval_receipt: Optional[ApprovalReceipt] = None,
    ) -> Union[LiveTransportPromotionResult, TransportPolicyBlock]:
        manifest = self._manifest_for_capability(request.capability_id)
        if manifest is None:
            return TransportPolicyBlock(reason="unknown_transport_capability")
        if request.transport_kind != manifest.kind.value:
            return TransportPolicyBlock(
                reason="transport_kind_mismatch",
                transport_id=manifest.transport_id,
            )
        if self._health.get(manifest.transport_id) != TransportHealth.healthy:
            return TransportPolicyBlock(
                reason="unhealthy_probe",
                transport_id=manifest.transport_id,
            )
        guard = LiveTransportPromotionGuard(
            live_transport_enabled=manifest.policy.live_transport,
        )
        return guard.evaluate(
            request,
            authority=authority,
            approval_receipt=approval_receipt,
        )

    def manifest_report(self) -> list[dict[str, object]]:
        return [
            _manifest_payload(self._manifests[transport_id])
            for transport_id in sorted(self._manifests)
        ]

    def health_report(self) -> dict[str, str]:
        return {
            transport_id: self._health[transport_id].value
            for transport_id in sorted(self._manifests)
        }

    def probe_report(self) -> list[dict[str, object]]:
        return [
            receipt.model_dump(mode="json")
            for receipt in self._probe_receipts
        ]

    def manifest_for_capability(
        self,
        capability_id: str,
    ) -> Optional[TransportAdapterManifest]:
        return self._manifest_for_capability(capability_id)

    def health_for_transport(self, transport_id: str) -> TransportHealth:
        transport_id_value = _require_non_empty(transport_id, "transport_id")
        return self._health.get(transport_id_value, TransportHealth.unknown)

    def summary(self) -> TransportRegistrySummary:
        live_transport = any(
            manifest.policy.live_transport for manifest in self._manifests.values()
        )
        return TransportRegistrySummary(
            transport_ids=tuple(sorted(self._manifests)),
            sandbox_probe_count=len(self._probe_receipts),
            live_transport=live_transport,
        )

    def _manifest_for_capability(
        self,
        capability_id: str,
    ) -> Optional[TransportAdapterManifest]:
        capability = _require_non_empty(capability_id, "capability_id")
        for manifest in self._manifests.values():
            if manifest.capability_id == capability:
                return manifest
        return None


def _manifest_payload(manifest: TransportAdapterManifest) -> dict[str, object]:
    return {
        "transport_id": manifest.transport_id,
        "kind": manifest.kind.value,
        "display_name": manifest.display_name,
        "capability_id": manifest.capability_id,
        "policy_labels": list(manifest.policy.policy_labels),
        "authority_requirements": [
            requirement.model_dump(mode="json")
            for requirement in manifest.policy.authority_requirements
        ],
        "credential_scope_label": manifest.policy.credential_scope_label,
        "live_transport": manifest.policy.live_transport,
        "sandbox_probe_ids": list(manifest.sandbox_probe_ids),
    }
