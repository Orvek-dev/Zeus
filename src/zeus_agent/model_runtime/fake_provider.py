from __future__ import annotations

from zeus_agent.model_runtime.interfaces import (
    ProviderMetadataEntry,
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
    ProviderUsage,
)
from zeus_agent.runtime_lease import RuntimeLeaseIntakeResult


class FakeProviderRuntime:
    def generate(
        self,
        request: ProviderRuntimeRequest,
        authorization: RuntimeLeaseIntakeResult,
    ) -> ProviderRuntimeResponse:
        return ProviderRuntimeResponse(
            decision="selected",
            provider_kind=request.provider_kind,
            provider_id=request.provider_id,
            model_id=request.model_id,
            response_id="resp_wave10_fake",
            content="fake provider dry-run response",
            usage=ProviderUsage(
                input_tokens=0,
                output_tokens=5,
                budget_units=1,
                latency_ms=0,
            ),
            metadata=(
                ProviderMetadataEntry(
                    key="capability.id",
                    value=authorization.capability_id,
                ),
                ProviderMetadataEntry(
                    key="lease.evidence_target",
                    value=authorization.evidence_target or "",
                ),
            ),
        )
