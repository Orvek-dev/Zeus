from __future__ import annotations

import re
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

from zeus_agent.security.credentials import redact_secret_spans

SurfaceKind = Literal[
    "provider",
    "mcp",
    "web",
    "github",
    "gateway",
    "browser",
    "terminal",
    "sandbox",
    "plugin",
]
RouteDecision = Literal["planned", "blocked"]
_REDACTED_SECRET_LABELS: Final = {"sk-...redacted", "[redacted-secret]"}
_FREE_TEXT_SECRET_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9._-]*"),
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"glpat-[A-Za-z0-9_-]+"),
    re.compile(r"xox[abp]-[A-Za-z0-9-]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r"(?is)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    ),
    re.compile(
        r"(?i)(api[ _-]?key|private[ _-]?key|token|password|secret)\s*[=:]\s*[^\s\"'}]+",
    ),
)


def _redact_identifier_secret_spans(value: str) -> str:
    redacted = redact_secret_spans(value)
    for label in _REDACTED_SECRET_LABELS:
        redacted = redacted.replace(label, "redacted")
    return redacted


class LiveConnectionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    request_id: str
    surface_kind: SurfaceKind
    capability_id: str
    dry_run: bool = True
    credential_scope: Optional[str] = None
    network_host: Optional[str] = None
    approval_receipt_id: Optional[str] = None
    source_pinned: bool = True
    mcp_description: Optional[str] = None
    sandbox_command: Optional[str] = None
    plugin_quarantined: bool = False
    gateway_target_allowed: bool = True
    evidence_target: str = "mneme.wave14.live_connection"

    @field_validator("request_id")
    @classmethod
    def _redact_request_id_secret_spans(cls, value: str) -> str:
        return _redact_identifier_secret_spans(value)

    @field_validator("credential_scope", "approval_receipt_id")
    @classmethod
    def _redact_secret_spans(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        redacted = redact_secret_spans(value)
        if redacted in _REDACTED_SECRET_LABELS:
            return "redacted-secret"
        return redacted

    @field_validator("mcp_description", "sandbox_command")
    @classmethod
    def _redact_free_text_secret_spans(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        redacted = value.strip()
        for pattern in _FREE_TEXT_SECRET_PATTERNS:
            redacted = pattern.sub("[redacted-secret]", redacted)
        return redacted


class RoutePlan(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    request_id: str
    surface_kind: SurfaceKind
    decision: RouteDecision
    reason: str
    dry_run: bool
    handler_executed: bool = False
    network_opened: bool = False

    @field_validator("request_id")
    @classmethod
    def _redact_request_id_secret_spans(cls, value: str) -> str:
        return _redact_identifier_secret_spans(value)


class LiveConnectionPlan(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
    )

    decision: RouteDecision
    routes: tuple[RoutePlan, ...]
    audit_record_created: bool
    handler_executed: bool
    network_opened: bool
    no_secret_echo: bool
    blocked_reasons: tuple[str, ...]

    @computed_field
    @property
    def route_count(self) -> int:
        return len(self.routes)

    @computed_field
    @property
    def planned_surface_kinds(self) -> tuple[SurfaceKind, ...]:
        return tuple(
            route.surface_kind
            for route in self.routes
            if route.decision == "planned"
        )
