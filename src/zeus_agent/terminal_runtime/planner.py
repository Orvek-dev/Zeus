from __future__ import annotations

from pathlib import Path
from typing import Final, Literal, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.capability_runtime.sandbox import SandboxPolicy
from zeus_agent.security.credentials import redact_secret_spans

TerminalPlanDecision = Literal["planned", "blocked"]

_STRICT_MODEL: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class EvidenceObligation(BaseModel):
    model_config = _STRICT_MODEL

    required: bool
    target: Optional[str] = None
    reason: str


class CleanupObligation(BaseModel):
    model_config = _STRICT_MODEL

    required: bool
    reason: str


class TerminalDispatchRequest(BaseModel):
    model_config = _STRICT_MODEL

    request_id: str = "terminal.dispatch"
    command: Union[str, tuple[str, ...]]
    root: Optional[Path] = None
    evidence_target: Optional[str] = None

    @field_validator("command", mode="before")
    @classmethod
    def _normalize_command(
        cls,
        value: Union[str, list[str], tuple[str, ...]],
    ) -> Union[str, tuple[str, ...]]:
        if isinstance(value, str):
            return redact_secret_spans(value.strip())
        if isinstance(value, list):
            return tuple(_redacted_text(item) for item in value)
        if isinstance(value, tuple):
            return tuple(_redacted_text(item) for item in value)
        raise ValueError("malformed_command")

    @field_validator("request_id", "evidence_target")
    @classmethod
    def _validate_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        redacted = redact_secret_spans(value.strip())
        if not redacted:
            raise ValueError("empty_terminal_dispatch_field")
        return redacted


class TerminalDispatchResult(BaseModel):
    model_config = _STRICT_MODEL

    decision: TerminalPlanDecision
    reason: str
    request_id: str
    command: str
    argv: tuple[str, ...]
    evidence_obligation: EvidenceObligation
    cleanup_obligation: CleanupObligation
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True


class TerminalDispatchFacade:
    def __init__(self, policy: Optional[SandboxPolicy] = None) -> None:
        self._policy = policy or SandboxPolicy()

    def plan(self, request: TerminalDispatchRequest) -> TerminalDispatchResult:
        root = request.root.resolve() if request.root is not None else Path.cwd()
        command_decision = self._policy.decide_command(request.command, root)
        if command_decision.decision == "allowed":
            decision: TerminalPlanDecision = "planned"
            reason = "dry_run_plan_only"
        else:
            decision = "blocked"
            reason = command_decision.reason or "blocked_by_policy"
        return TerminalDispatchResult(
            decision=decision,
            reason=reason,
            request_id=request.request_id,
            command=_command_text(request.command),
            argv=tuple(redact_secret_spans(value) for value in command_decision.argv),
            evidence_obligation=EvidenceObligation(
                required=True,
                target=request.evidence_target,
                reason="terminal_dispatch_requires_evidence",
            ),
            cleanup_obligation=CleanupObligation(
                required=False,
                reason="terminal_facade_starts_no_process",
            ),
        )


TerminalDispatchPlanner = TerminalDispatchFacade
TerminalFacade = TerminalDispatchFacade


def plan_terminal_dispatch(
    request: Union[TerminalDispatchRequest, str, Sequence[str]],
    *,
    root: Optional[Path] = None,
    evidence_target: Optional[str] = None,
) -> TerminalDispatchResult:
    if isinstance(request, TerminalDispatchRequest):
        dispatch_request = request
    elif isinstance(request, str):
        dispatch_request = TerminalDispatchRequest(
            command=request,
            root=root,
            evidence_target=evidence_target,
        )
    else:
        dispatch_request = TerminalDispatchRequest(
            command=tuple(request),
            root=root,
            evidence_target=evidence_target,
        )
    return TerminalDispatchFacade().plan(dispatch_request)


def _redacted_text(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("malformed_command")
    return redact_secret_spans(value.strip())


def _command_text(command: Union[str, tuple[str, ...]]) -> str:
    if isinstance(command, str):
        return command
    if isinstance(command, tuple):
        return " ".join(command)
    raise TypeError(f"unsupported_terminal_command:{type(command).__name__}")


__all__: Final = (
    "CleanupObligation",
    "EvidenceObligation",
    "TerminalDispatchFacade",
    "TerminalDispatchPlanner",
    "TerminalDispatchRequest",
    "TerminalDispatchResult",
    "TerminalFacade",
    "TerminalPlanDecision",
    "plan_terminal_dispatch",
)
