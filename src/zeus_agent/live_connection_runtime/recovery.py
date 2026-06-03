from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_serializer, field_validator

from .trace import LiveConnectionTrace, redact_live_connection_text

CleanupReceiptDecision = Literal["completed", "skipped"]

_MODEL_CONFIG: Final = ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
)


class ReplayRequest(BaseModel):
    model_config = _MODEL_CONFIG

    replay_id: str
    trace_id: str
    from_step_id: str
    reason: str
    dry_run: bool = True
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True

    @field_validator("replay_id", "trace_id", "from_step_id", "reason")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_text(value, _field_name(info))

    @field_validator("handler_executed", "network_opened")
    @classmethod
    def _reject_side_effect_claim(cls, value: bool) -> bool:
        if value:
            raise ValueError("side_effect_claim_not_allowed")
        return False

    @field_serializer("replay_id", "trace_id", "from_step_id", "reason")
    def _serialize_text(self, value: str) -> str:
        return redact_live_connection_text(value)


class CleanupObligation(BaseModel):
    model_config = _MODEL_CONFIG

    obligation_id: str
    trace_id: str
    step_id: str
    reason: str
    required: bool = True
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True

    @field_validator("obligation_id", "trace_id", "step_id", "reason")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_text(value, _field_name(info))

    @field_validator("handler_executed", "network_opened")
    @classmethod
    def _reject_side_effect_claim(cls, value: bool) -> bool:
        if value:
            raise ValueError("side_effect_claim_not_allowed")
        return False

    @field_serializer("obligation_id", "trace_id", "step_id", "reason")
    def _serialize_text(self, value: str) -> str:
        return redact_live_connection_text(value)


class CleanupReceipt(BaseModel):
    model_config = _MODEL_CONFIG

    receipt_id: str
    obligation_id: str
    trace_id: str
    step_id: str
    cleanup_decision: CleanupReceiptDecision
    reason: str
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True

    @field_validator("receipt_id", "obligation_id", "trace_id", "step_id", "reason")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_text(value, _field_name(info))

    @field_validator("handler_executed", "network_opened")
    @classmethod
    def _reject_side_effect_claim(cls, value: bool) -> bool:
        if value:
            raise ValueError("side_effect_claim_not_allowed")
        return False

    @field_serializer("receipt_id", "obligation_id", "trace_id", "step_id", "reason")
    def _serialize_text(self, value: str) -> str:
        return redact_live_connection_text(value)


def make_replay_request(
    trace: LiveConnectionTrace,
    *,
    replay_id: str,
    from_step_id: str,
    reason: str,
) -> ReplayRequest:
    step_id = _require_known_step(trace, from_step_id)
    return ReplayRequest(
        replay_id=replay_id,
        trace_id=trace.trace_id,
        from_step_id=step_id,
        reason=reason,
        dry_run=True,
        handler_executed=False,
        network_opened=False,
        no_secret_echo=True,
    )


def make_cleanup_obligation(
    trace: LiveConnectionTrace,
    *,
    obligation_id: str,
    step_id: str,
    reason: str,
) -> CleanupObligation:
    safe_step_id = _require_known_step(trace, step_id)
    return CleanupObligation(
        obligation_id=obligation_id,
        trace_id=trace.trace_id,
        step_id=safe_step_id,
        reason=reason,
        required=True,
        handler_executed=False,
        network_opened=False,
        no_secret_echo=True,
    )


def make_cleanup_receipt(
    obligation: CleanupObligation,
    *,
    receipt_id: str,
    decision: CleanupReceiptDecision,
    reason: str,
) -> CleanupReceipt:
    return CleanupReceipt(
        receipt_id=receipt_id,
        obligation_id=obligation.obligation_id,
        trace_id=obligation.trace_id,
        step_id=obligation.step_id,
        cleanup_decision=decision,
        reason=reason,
        handler_executed=False,
        network_opened=False,
        no_secret_echo=True,
    )


def _require_known_step(trace: LiveConnectionTrace, step_id: str) -> str:
    safe_step_id = _require_text(step_id, "step_id")
    if safe_step_id not in trace.step_ids:
        raise ValueError("unknown_trace_step")
    return safe_step_id


def _require_text(value: str, field_name: str) -> str:
    redacted = redact_live_connection_text(value)
    if redacted == "":
        raise ValueError(f"{field_name}_empty")
    return redacted


def _field_name(info: ValidationInfo) -> str:
    if info.field_name is None:
        return "value"
    return info.field_name
