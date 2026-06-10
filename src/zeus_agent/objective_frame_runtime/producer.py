from __future__ import annotations

import json
from typing import Callable, Final, Optional

from pydantic import ValidationError

from zeus_agent.objective_card_runtime import ObjectiveFrameInput
from zeus_agent.provider_capability_runtime import (
    CanonicalProviderHandler,
    ProviderRequest,
    ProviderVendor,
)
from zeus_agent.security.credentials import contains_secret_material, redact_secret_spans

from .models import FrameParseResult

# The LLM boundary: an utterance in, raw model text out. Everything downstream is
# deterministic. Injecting this seam keeps the autonomy path fully testable.
GenerateFn = Callable[[str], str]

_FRAME_INSTRUCTION: Final = (
    "You are Zeus's objective compiler. Read the user's request and return ONLY a JSON "
    "object with keys: normalized_objective (string), triage "
    "(chat|oneshot|project|automation), unknowns (array), candidates (non-empty array of "
    "workflow DAGs), required_criteria (array). Do not include secrets. Request: "
)


def parse_frame(raw: str) -> "FrameParseResult":

    text = raw.strip()
    if text == "":
        return FrameParseResult(decision="blocked", blocked_reason="empty_frame_output")
    if contains_secret_material(text):
        return FrameParseResult(
            decision="blocked",
            blocked_reason="raw_secret_in_frame",
            no_secret_echo=not contains_secret_material(redact_secret_spans(text)),
        )
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return FrameParseResult(decision="blocked", blocked_reason="malformed_frame_json")
    if not isinstance(parsed, dict):
        return FrameParseResult(decision="blocked", blocked_reason="malformed_frame_json")
    try:
        frame = ObjectiveFrameInput.model_validate(parsed)
    except ValidationError:
        return FrameParseResult(decision="blocked", blocked_reason="malformed_objective_frame")
    return FrameParseResult(decision="frame", frame=frame)


def produce_frame(*, utterance: str, generate: GenerateFn) -> "FrameParseResult":

    safe = utterance.strip()
    if safe == "":
        return FrameParseResult(decision="blocked", blocked_reason="empty_utterance")
    if contains_secret_material(safe):
        return FrameParseResult(decision="blocked", blocked_reason="raw_secret_in_utterance")
    raw = generate(_FRAME_INSTRUCTION + safe)
    return parse_frame(raw)


def provider_generate(
    handler: CanonicalProviderHandler,
    *,
    vendor: ProviderVendor = ProviderVendor.fake,
    model_id: str = "fake.frame.model",
    endpoint: Optional[str] = None,
    secret_ref: Optional[str] = None,
    allowed_models: tuple[str, ...] = (),
    allowed_hosts: tuple[str, ...] = (),
    lease=None,
    approval=None,
    approval_envelope=None,
) -> GenerateFn:
    """Adapt the canonical provider handler into the GenerateFn seam — the real
    autonomy path. External vendors still require explicit lease+approval (the
    provider handler enforces it)."""

    def generate(prompt: str) -> str:
        receipt = handler.generate(
            ProviderRequest(
                vendor=vendor,
                model_id=model_id,
                message=prompt,
                endpoint=endpoint,
                secret_ref=secret_ref,
                allowed_models=allowed_models,
                allowed_hosts=allowed_hosts,
            ),
            lease=lease,
            approval=approval,
            approval_envelope=approval_envelope,
        )
        return receipt.content or ""

    return generate
