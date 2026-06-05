from __future__ import annotations

from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationInfo, field_serializer, field_validator, model_validator

from zeus_agent.gateway_runtime.persistence import require_public_identifier
from zeus_agent.security.credentials import redact_secret_spans

GatewayDecision = Literal["allowed", "blocked"]
GatewayReason = Literal[
    "allowed",
    "unauthenticated",
    "non_loopback_blocked",
    "webhook_blocked",
    "external_delivery_blocked",
    "standing_order_blocked",
    "malformed_request",
    "idempotency_conflict",
]
JsonObject = dict[str, JsonValue]

_MODEL_CONFIG: Final = ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    strict=True,
)
_REDACTED_SECRET: Final = "[redacted-secret]"
_PUBLIC_IDENTITY_FIELDS: Final = frozenset(("session_id", "run_id", "goal_contract_id"))


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


def _redact_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return redact_secret_spans(value)


class _GatewayModel(BaseModel):
    model_config = _MODEL_CONFIG

    def safe_dump(self) -> JsonObject:
        return self.model_dump(mode="json")


class GatewaySessionCreateRequest(_GatewayModel):
    session_id: str
    run_id: str
    goal_contract_id: str
    resume_token: str = Field(repr=False)
    message: str

    @field_validator("session_id", "run_id", "goal_contract_id", "resume_token", "message")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        normalized = _require_non_empty(value, info.field_name)
        if info.field_name in _PUBLIC_IDENTITY_FIELDS:
            return require_public_identifier(normalized, info.field_name)
        return normalized

    @field_serializer("resume_token")
    def _serialize_resume_token(self, value: str) -> str:
        return _redact_required_secret(value)

    @field_serializer("message")
    def _serialize_message(self, value: str) -> str:
        return redact_secret_spans(value)

    def no_secret_echo(self) -> bool:
        return self.resume_token not in self.model_dump_json()


class GatewaySessionResumeRequest(_GatewayModel):
    resume_token: str = Field(repr=False)
    message: str

    @field_validator("resume_token", "message")
    @classmethod
    def _validate_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)

    @field_serializer("resume_token")
    def _serialize_resume_token(self, value: str) -> str:
        return _redact_required_secret(value)

    @field_serializer("message")
    def _serialize_message(self, value: str) -> str:
        return redact_secret_spans(value)

    def no_secret_echo(self) -> bool:
        return self.resume_token not in self.model_dump_json()


class GatewayApiResponse(_GatewayModel):
    decision: GatewayDecision
    reason: GatewayReason
    status_code: int = Field(ge=100, le=599)
    session_id: Optional[str] = None
    run_id: Optional[str] = None
    goal_contract_id: Optional[str] = None
    session_persisted: bool = False
    resume_succeeded: bool = False
    loopback_http_opened: bool = False
    audit_record_created: bool = False
    audit_records: int = Field(default=0, ge=0)
    gateway_session_count: int = Field(default=0, ge=0)
    idempotency_replay_stable: bool = False
    idempotent_replay: bool = False
    request_count: int = Field(default=0, ge=0)
    response_count: int = Field(default=0, ge=0)
    side_effect_count: int = Field(default=0, ge=0)
    handler_executed: bool = False
    network_opened: bool = False
    external_delivery_attempted: bool = False
    external_delivery_opened: bool = False
    webhook_registered: bool = False
    standing_order_created: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    @classmethod
    def allowed(
        cls,
        *,
        reason: Literal["allowed"] = "allowed",
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
        goal_contract_id: Optional[str] = None,
        session_persisted: bool = False,
        resume_succeeded: bool = False,
        loopback_http_opened: bool = False,
        audit_record_created: bool = False,
        audit_records: int = 0,
        gateway_session_count: int = 0,
        idempotency_replay_stable: bool = False,
        idempotent_replay: bool = False,
        request_count: int = 0,
        response_count: int = 0,
        side_effect_count: int = 0,
        handler_executed: bool = False,
        network_opened: bool = False,
        external_delivery_attempted: bool = False,
        external_delivery_opened: bool = False,
        webhook_registered: bool = False,
        standing_order_created: bool = False,
        credential_material_accessed: bool = False,
    ) -> GatewayApiResponse:
        replay_stable = idempotency_replay_stable or idempotent_replay
        return cls(
            decision="allowed",
            reason=reason,
            status_code=200,
            session_id=session_id,
            run_id=run_id,
            goal_contract_id=goal_contract_id,
            session_persisted=session_persisted,
            resume_succeeded=resume_succeeded,
            loopback_http_opened=loopback_http_opened,
            audit_record_created=audit_record_created,
            audit_records=audit_records,
            gateway_session_count=gateway_session_count,
            idempotency_replay_stable=replay_stable,
            idempotent_replay=replay_stable,
            request_count=request_count,
            response_count=response_count,
            side_effect_count=side_effect_count,
            handler_executed=handler_executed,
            network_opened=network_opened,
            external_delivery_attempted=external_delivery_attempted,
            external_delivery_opened=external_delivery_opened,
            webhook_registered=webhook_registered,
            standing_order_created=standing_order_created,
            credential_material_accessed=credential_material_accessed,
        )

    @classmethod
    def blocked(
        cls,
        *,
        reason: ExcludingAllowedReason,
        status_code: int = 403,
    ) -> GatewayApiResponse:
        return cls(
            decision="blocked",
            reason=reason,
            status_code=status_code,
            handler_executed=False,
        )

    @field_validator("session_id", "run_id", "goal_contract_id")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, info.field_name)

    @field_validator("live_production_claimed")
    @classmethod
    def _validate_no_live_claim(cls, value: bool) -> bool:
        if value:
            raise ValueError("live_production_claimed_forbidden")
        return value

    @field_serializer("session_id", "run_id", "goal_contract_id")
    def _serialize_optional_identity(self, value: Optional[str]) -> Optional[str]:
        return _redact_optional(value)

    @model_validator(mode="after")
    def _validate_decision_status(self) -> GatewayApiResponse:
        if self.decision == "allowed":
            if not 200 <= self.status_code <= 299:
                raise ValueError("allowed_status_must_be_2xx")
            return self
        if self.decision == "blocked":
            if not 400 <= self.status_code <= 499:
                raise ValueError("blocked_status_must_be_4xx")
            if self.handler_executed:
                raise ValueError("blocked_handler_executed")
            if self.side_effect_count != 0:
                raise ValueError("blocked_side_effect_count")
            if any(
                (
                    self.session_persisted,
                    self.resume_succeeded,
                    self.loopback_http_opened,
                    self.idempotency_replay_stable,
                    self.idempotent_replay,
                    self.network_opened,
                    self.external_delivery_attempted,
                    self.external_delivery_opened,
                    self.webhook_registered,
                    self.standing_order_created,
                    self.credential_material_accessed,
                ),
            ):
                raise ValueError("blocked_side_effect_flag")
            return self
        raise AssertionError(self.decision)


ExcludingAllowedReason = Literal[
    "unauthenticated",
    "non_loopback_blocked",
    "webhook_blocked",
    "external_delivery_blocked",
    "standing_order_blocked",
    "malformed_request",
    "idempotency_conflict",
]


def _redact_required_secret(value: str) -> str:
    _require_non_empty(value, "secret")
    return _REDACTED_SECRET


__all__: Final = (
    "ExcludingAllowedReason",
    "GatewayApiResponse",
    "GatewayDecision",
    "GatewayReason",
    "GatewaySessionCreateRequest",
    "GatewaySessionResumeRequest",
)
