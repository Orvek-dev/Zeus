from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from zeus_agent.security.credentials import (
    CredentialScope,
    CredentialScopeUnsafeError,
    redact_secret_like,
)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


def _credential_scope_label(raw_value: Optional[str]) -> Optional[str]:
    if raw_value is None:
        return None
    try:
        return CredentialScope.parse(raw_value).label
    except CredentialScopeUnsafeError as exc:
        raise ValueError(exc.payload["reason"]) from exc


class TransportKind(str, Enum):
    provider = "provider"
    mcp = "mcp"
    api = "api"
    plugin = "plugin"


class TransportHealth(str, Enum):
    unknown = "unknown"
    healthy = "healthy"
    unhealthy = "unhealthy"


class AuthorityRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    capability_id: str
    network_host: Optional[str] = None
    credential_scope: Optional[str] = None

    @field_validator("capability_id")
    @classmethod
    def _validate_capability_id(cls, value: str) -> str:
        return _require_non_empty(value, "capability_id")

    @field_validator("network_host")
    @classmethod
    def _validate_network_host(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, "network_host")

    @field_validator("credential_scope")
    @classmethod
    def _validate_credential_scope(cls, value: Optional[str]) -> Optional[str]:
        return _credential_scope_label(value)


class TransportPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    policy_labels: tuple[str, ...]
    authority_requirements: tuple[AuthorityRequirement, ...]
    credential_scope_label: Optional[str] = None
    live_transport: bool = False

    @field_validator("policy_labels")
    @classmethod
    def _validate_policy_labels(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        labels = tuple(_require_non_empty(value, "policy_labels") for value in values)
        if not labels:
            raise ValueError("policy_labels must be non-empty")
        return labels

    @field_validator("authority_requirements")
    @classmethod
    def _validate_authority_requirements(
        cls,
        values: tuple[AuthorityRequirement, ...],
    ) -> tuple[AuthorityRequirement, ...]:
        if not values:
            raise ValueError("authority_requirements must be non-empty")
        return values

    @field_validator("credential_scope_label")
    @classmethod
    def _validate_credential_scope_label(cls, value: Optional[str]) -> Optional[str]:
        return _credential_scope_label(value)

    @field_validator("live_transport")
    @classmethod
    def _validate_live_transport(cls, value: bool) -> bool:
        if value:
            raise ValueError("live_transport_not_authorized")
        return False


class TransportAdapterManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    transport_id: str
    kind: TransportKind
    display_name: str
    capability_id: str
    policy: TransportPolicy
    sandbox_probe_ids: tuple[str, ...] = ()

    @field_validator("transport_id", "display_name", "capability_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("sandbox_probe_ids")
    @classmethod
    def _validate_probe_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, "sandbox_probe_ids") for value in values)


class TransportPolicyBlock(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    reason: str
    transport_id: Optional[str] = None
    handler_executed: bool = False
    network_opened: bool = False
    redacted_input: Optional[str] = None

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        return _require_non_empty(value, "reason")

    @field_validator("redacted_input")
    @classmethod
    def _validate_redacted_input(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return redact_secret_like(_require_non_empty(value, "redacted_input"))

    @field_serializer("redacted_input")
    def _serialize_redacted_input(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return redact_secret_like(value)

    def model_copy(
        self,
        *,
        update: dict[str, object] | None = None,
        deep: bool = False,
    ) -> "TransportPolicyBlock":
        if update is None:
            return super().model_copy(update=None, deep=deep)
        safe_update = dict(update)
        value = safe_update.get("redacted_input")
        if isinstance(value, str):
            safe_update["redacted_input"] = redact_secret_like(value)
        return super().model_copy(update=safe_update, deep=deep)
