from __future__ import annotations

from pathlib import Path
from typing import Final, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.security.credentials import redact_secret_spans

SandboxPlanDecision = Literal["planned", "blocked"]
RequirementDecision = Literal["planned", "blocked"]

_STRICT_MODEL: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class EvidenceObligation(BaseModel):
    model_config = _STRICT_MODEL

    required: bool
    target: Optional[str] = None
    reason: str


class CleanupObligation(BaseModel):
    model_config = _STRICT_MODEL

    required: bool
    decision: RequirementDecision
    reason: str
    plan: Optional[str] = None


class SandboxRequirement(BaseModel):
    model_config = _STRICT_MODEL

    name: str
    value: str
    decision: RequirementDecision
    reason: Optional[str] = None


class SandboxMountRequirement(BaseModel):
    model_config = _STRICT_MODEL

    path: str
    decision: RequirementDecision
    resolved_path: Optional[str] = None
    reason: Optional[str] = None


class SandboxCommandPlan(BaseModel):
    model_config = _STRICT_MODEL

    command: str
    argv: tuple[str, ...]
    decision: Literal["allowed", "blocked"]
    reason: Optional[str] = None


class SandboxDispatchRequest(BaseModel):
    model_config = _STRICT_MODEL

    request_id: str = "sandbox.dispatch"
    backend: str = "local"
    root: Optional[Path] = None
    mounts: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()
    egress_policy: str = "none"
    resource_profile: str = "bounded"
    cleanup_required: bool = True
    cleanup_plan: Optional[str] = None
    evidence_target: Optional[str] = None

    @field_validator("mounts", "commands", mode="before")
    @classmethod
    def _normalize_text_tuple(cls, value: Union[str, list[str], tuple[str, ...]]) -> tuple[str, ...]:
        if isinstance(value, str):
            return (redact_secret_spans(value),)
        if isinstance(value, list):
            return tuple(_redacted_text(item) for item in value)
        if isinstance(value, tuple):
            return tuple(_redacted_text(item) for item in value)
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
    def _validate_text(cls, value: Optional[str]) -> Optional[str]:
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
