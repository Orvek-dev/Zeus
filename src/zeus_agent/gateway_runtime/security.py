from __future__ import annotations

import hmac
import hashlib
from dataclasses import dataclass
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_serializer, field_validator

from zeus_agent.gateway_runtime.models import GatewayApiResponse

GatewaySurface = Literal["session", "audit", "webhook", "external_delivery", "standing_order", "unknown"]

_MODEL_CONFIG: Final = ConfigDict(
    extra="forbid",
    frozen=True,
    hide_input_in_errors=True,
    strict=True,
)
_REDACTED_SECRET: Final = "[redacted-secret]"
_AUTHORITY_HASH_PREFIX: Final = "sha256:"
_LOOPBACK_HOSTS: Final = frozenset(("127.0.0.1", "localhost", "::1"))
_SESSION_PATHS: Final = frozenset(
    ("/gateway/session/create", "/gateway/session/resume", "/v1/gateway/sessions"),
)
_V1_SESSION_PREFIX: Final = "/v1/gateway/sessions/"
_V1_SESSION_RESUME_SUFFIX: Final = "/resume"
_AUDIT_PATHS: Final = frozenset(("/v1/gateway/audit",))


class GatewaySecurityRequestContext(BaseModel):
    model_config = _MODEL_CONFIG

    method: str
    path: str
    host: str
    client_host: str
    authorization_header: Optional[str] = Field(default=None, repr=False)
    expected_token: str = Field(repr=False)

    @field_validator("method")
    @classmethod
    def _validate_method(cls, value: str) -> str:
        return _require_non_empty(value, "method").upper()

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        normalized = _require_non_empty(value, "path")
        if not normalized.startswith("/"):
            raise ValueError("malformed_request")
        return normalized

    @field_validator("host", "client_host", "expected_token")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("authorization_header")
    @classmethod
    def _validate_authorization_header(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if normalized == "":
            return None
        return normalized

    @field_serializer("authorization_header", "expected_token")
    def _serialize_secret(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _REDACTED_SECRET


@dataclass(frozen=True)
class GatewaySecurityPolicy:
    def authorize_loopback(self, context: GatewaySecurityRequestContext) -> GatewayApiResponse:
        if not _is_loopback(context.host) or not _is_loopback(context.client_host):
            return GatewayApiResponse.blocked(
                reason="non_loopback_blocked",
                status_code=403,
            )
        if not _is_authenticated(context.authorization_header, context.expected_token):
            return GatewayApiResponse.blocked(reason="unauthenticated", status_code=401)
        surface = _surface_for_path(context.path)
        if surface == "session":
            if context.method != "POST":
                return GatewayApiResponse.blocked(reason="malformed_request", status_code=400)
            return GatewayApiResponse.allowed(reason="allowed")
        if surface == "audit":
            if context.method != "GET":
                return GatewayApiResponse.blocked(reason="malformed_request", status_code=400)
            return GatewayApiResponse.allowed(reason="allowed")
        if surface == "webhook":
            return GatewayApiResponse.blocked(reason="webhook_blocked", status_code=403)
        if surface == "external_delivery":
            return GatewayApiResponse.blocked(
                reason="external_delivery_blocked",
                status_code=403,
            )
        if surface == "standing_order":
            return GatewayApiResponse.blocked(
                reason="standing_order_blocked",
                status_code=403,
            )
        if surface == "unknown":
            return GatewayApiResponse.blocked(reason="malformed_request", status_code=400)
        raise AssertionError(surface)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


def gateway_authority_fingerprint(context: GatewaySecurityRequestContext) -> str:
    token = _bearer_token(context.authorization_header)
    normalized = _require_non_empty(token or "", "authorization_header")
    return _AUTHORITY_HASH_PREFIX + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _is_authenticated(authorization_header: Optional[str], expected_token: str) -> bool:
    token = _bearer_token(authorization_header)
    if token is None:
        return False
    return hmac.compare_digest(token, expected_token)


def _bearer_token(authorization_header: Optional[str]) -> Optional[str]:
    if authorization_header is None:
        return None
    prefix, separator, token = authorization_header.strip().partition(" ")
    if separator == "" or prefix.lower() != "bearer":
        return None
    normalized = token.strip()
    if normalized == "":
        return None
    return normalized


def _is_loopback(raw_host: str) -> bool:
    return _host_name(raw_host) in _LOOPBACK_HOSTS


def _host_name(raw_host: str) -> str:
    normalized = raw_host.strip().lower()
    if normalized == "::1":
        return normalized
    if normalized.startswith("[::1]"):
        return "::1"
    if ":" in normalized:
        return normalized.partition(":")[0]
    return normalized


def _surface_for_path(path: str) -> GatewaySurface:
    normalized = path.rstrip("/") or "/"
    if normalized in _SESSION_PATHS or _is_v1_session_resume_path(normalized):
        return "session"
    if normalized in _AUDIT_PATHS:
        return "audit"
    if normalized.startswith(("/gateway/webhook", "/webhook", "/v1/gateway/webhooks")):
        return "webhook"
    if normalized.startswith(
        ("/gateway/external-delivery", "/external-delivery", "/v1/gateway/external-delivery"),
    ):
        return "external_delivery"
    if normalized.startswith(("/gateway/standing-order", "/standing-order", "/v1/gateway/standing-orders")):
        return "standing_order"
    return "unknown"


def _is_v1_session_resume_path(path: str) -> bool:
    if not path.startswith(_V1_SESSION_PREFIX) or not path.endswith(_V1_SESSION_RESUME_SUFFIX):
        return False
    session_id = path.removeprefix(_V1_SESSION_PREFIX).removesuffix(_V1_SESSION_RESUME_SUFFIX)
    return session_id != "" and "/" not in session_id


__all__: Final = (
    "gateway_authority_fingerprint",
    "GatewaySecurityPolicy",
    "GatewaySecurityRequestContext",
    "GatewaySurface",
)
