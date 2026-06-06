from __future__ import annotations

import json

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
        if request.metadata_value("zeus.intent_schema") is True:
            return _intent_frame_response(request, authorization)
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


def _intent_frame_response(
    request: ProviderRuntimeRequest,
    authorization: RuntimeLeaseIntakeResult,
) -> ProviderRuntimeResponse:
    user_message = next(
        (message.content for message in request.messages if message.role == "user"),
        "Help Zeus understand the user's objective.",
    )
    content = json.dumps(
        {
            "desired_outcome": user_message.strip(),
            "acceptance_criteria": [
                "Zeus produces an IntentFrame with acceptance criteria, unknowns, and evidence obligations.",
                "Zeus keeps live-capable work behind lease, approval, credential scope, and audit gates.",
            ],
            "constraints": ["local-first", "approval", "lease", "audit", "no raw secrets"],
            "entities": ["zeus", "provider", "workflow"],
        },
        sort_keys=True,
    )
    return ProviderRuntimeResponse(
        decision="selected",
        provider_kind=request.provider_kind,
        provider_id=request.provider_id,
        model_id=request.model_id,
        response_id="resp_v310_fake_intent",
        content=content,
        usage=ProviderUsage(
            input_tokens=len(user_message.split()),
            output_tokens=len(content.split()),
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
            ProviderMetadataEntry(key="zeus.intent_schema", value=True),
        ),
    )
