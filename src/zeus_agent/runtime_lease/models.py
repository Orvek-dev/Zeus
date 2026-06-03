from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from zeus_agent.security.credentials import CredentialScope, CredentialScopeUnsafeError

_ID_PATTERN: Final = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_HOST_PATTERN: Final = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
_ISSUED_AT: Final = datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)
_EXPIRES_AT: Final = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


def _validate_scoped_id(value: str, field_name: str) -> str:
    normalized = _require_non_empty(value, field_name)
    if _ID_PATTERN.fullmatch(normalized) is None:
        raise ValueError("malformed_{0}".format(field_name.removesuffix("_id")))
    return normalized


def _validate_host(value: str) -> str:
    normalized = _require_non_empty(value, "network_hosts")
    if _HOST_PATTERN.fullmatch(normalized) is None:
        raise ValueError("malformed_network_host")
    return normalized


def _credential_scope_label(value: str) -> str:
    try:
        return CredentialScope.parse(value).label
    except CredentialScopeUnsafeError as exc:
        raise ValueError("unsafe_credential") from exc
    except ValueError as exc:
        raise ValueError("malformed_credential_scope") from exc


class RuntimeLease(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    lease_id: str
    objective_id: str
    principal_id: str
    run_id: str
    allowed_capabilities: tuple[str, ...]
    credential_scopes: tuple[str, ...] = ()
    network_hosts: tuple[str, ...] = ()
    budget_limit: int = Field(gt=0)
    evidence_target: str
    live_transport_allowed: bool = False
    issued_at: datetime = _ISSUED_AT
    expires_at: datetime = _EXPIRES_AT

    @field_validator("lease_id", "objective_id", "principal_id", "run_id")
    @classmethod
    def _validate_ids(cls, value: str, info: ValidationInfo) -> str:
        return _validate_scoped_id(value, info.field_name)

    @field_validator("evidence_target")
    @classmethod
    def _validate_evidence_target(cls, value: str) -> str:
        return _validate_scoped_id(value, "evidence_target")

    @field_validator("allowed_capabilities")
    @classmethod
    def _validate_capabilities(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("allowed_capabilities must be non-empty")
        return tuple(_validate_scoped_id(value, "capability_id") for value in values)

    @field_validator("credential_scopes")
    @classmethod
    def _validate_credential_scopes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_credential_scope_label(value) for value in values)

    @field_validator("network_hosts")
    @classmethod
    def _validate_network_hosts(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_validate_host(value) for value in values)

    @field_validator("issued_at", "expires_at")
    @classmethod
    def _validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _validate_time_window(self) -> RuntimeLease:
        if self.expires_at <= self.issued_at:
            raise ValueError("runtime_lease_expired")
        return self

    def no_secret_echo(self) -> bool:
        serialized = self.model_dump_json()
        return "sk-" not in serialized and "ghp_" not in serialized


def wave9_fixture_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave9.lease.fixture",
        objective_id="wave9.objective.runtime_lease",
        principal_id="wave9.principal.worker_a",
        run_id="wave9.run.fixture",
        allowed_capabilities=(
            "provider.external.generate",
            "mcp.echo",
            "web.search",
            "github.repo.inspect",
            "gateway.webhook.dispatch",
            "browser.page.inspect",
            "terminal.run",
            "sandbox.remote.execute",
            "cron.schedule.tick",
            "api.tool.invoke",
            "plugin.local.execute",
        ),
        credential_scopes=(
            "external.openai.readonly",
            "external.github.readonly",
            "external.gateway.readonly",
        ),
        network_hosts=(
            "api.openai.local",
            "github.local",
            "gateway.local",
        ),
        budget_limit=10_000,
        evidence_target="mneme.wave9.runtime_lease",
    )
