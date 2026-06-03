from __future__ import annotations

from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.security.credentials import redact_secret_spans

SandboxPlanDecision = Literal["planned", "blocked"]
RequirementDecision = Literal["planned", "blocked"]

_STRICT_MODEL: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class EvidenceObligation(BaseModel):
    model_config = _STRICT_MODEL

    required: bool
    target: str | None = None
    reason: str


class CleanupObligation(BaseModel):
    model_config = _STRICT_MODEL

    required: bool
    decision: RequirementDecision
    reason: str
    plan: str | None = None


class SandboxRequirement(BaseModel):
    model_config = _STRICT_MODEL

    name: str
    value: str
    decision: RequirementDecision
    reason: str | None = None


class SandboxMountRequirement(BaseModel):
    model_config = _STRICT_MODEL

    path: str
    decision: RequirementDecision
    resolved_path: str | None = None
    reason: str | None = None


class SandboxCommandPlan(BaseModel):
    model_config = _STRICT_MODEL

    command: str
    argv: tuple[str, ...]
    decision: Literal["allowed", "blocked"]
    reason: str | None = None


class SandboxDispatchRequest(BaseModel):
    model_config = _STRICT_MODEL

    request_id: str = "sandbox.dispatch"
    backend: str = "local"
    root: Path | None = None
    mounts: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()
    egress_policy: str = "none"
    resource_profile: str = "bounded"
    cleanup_required: bool = True
    cleanup_plan: str | None = None
    evidence_target: str | None = None

    @field_validator("mounts", "commands", mode="before")
    @classmethod
    def _normalize_text_tuple(cls, value: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
        match value:
            case str():
                return (redact_secret_spans(value),)
            case list():
                return tuple(_redacted_text(item) for item in value)
            case tuple():
                return tuple(_redacted_text(item) for item in value)
            case _:
                raise ValueError("malformed_text_tuple")

    @field_validator(
        "request_id",
        "backend",
        "egress_policy",
        "resource_profile",
        "cleanup_plan",
        "evidence_target",
    )
    @classmethod
    def _validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        redacted = redact_secret_spans(value.strip())
        if not redacted:
            raise ValueError("empty_sandbox_dispatch_field")
        return redacted


class SandboxDispatchResult(BaseModel):
    model_config = _STRICT_MODEL

    decision: SandboxPlanDecision
    reason: str
    request_id: str
    backend_requirement: SandboxRequirement
    mount_requirements: tuple[SandboxMountRequirement, ...]
    egress_requirement: SandboxRequirement
    resource_requirement: SandboxRequirement
    cleanup_obligation: CleanupObligation
    evidence_obligation: EvidenceObligation
    command_plans: tuple[SandboxCommandPlan, ...]
    blocked_reasons: tuple[str, ...]
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True


def _redacted_text(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("malformed_text")
    return redact_secret_spans(value)


__all__: Final = (
    "CleanupObligation",
    "EvidenceObligation",
    "RequirementDecision",
    "SandboxCommandPlan",
    "SandboxDispatchRequest",
    "SandboxDispatchResult",
    "SandboxMountRequirement",
    "SandboxPlanDecision",
    "SandboxRequirement",
)
