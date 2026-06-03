from __future__ import annotations

from pathlib import Path
from typing import Final, Literal, Sequence, assert_never

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.capability_runtime.sandbox import SandboxPolicy
from zeus_agent.security.credentials import redact_secret_spans

TerminalPlanDecision = Literal["planned", "blocked"]

_STRICT_MODEL: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class EvidenceObligation(BaseModel):
    model_config = _STRICT_MODEL

    required: bool
    target: str | None = None
    reason: str


class CleanupObligation(BaseModel):
    model_config = _STRICT_MODEL

    required: bool
    reason: str


class TerminalDispatchRequest(BaseModel):
    model_config = _STRICT_MODEL

    request_id: str = "terminal.dispatch"
    command: str | tuple[str, ...]
    root: Path | None = None
    evidence_target: str | None = None

    @field_validator("command", mode="before")
    @classmethod
    def _normalize_command(cls, value: str | list[str] | tuple[str, ...]) -> str | tuple[str, ...]:
        match value:
            case str():
                return redact_secret_spans(value.strip())
            case list():
                return tuple(_redacted_text(item) for item in value)
            case tuple():
                return tuple(_redacted_text(item) for item in value)
            case _:
                raise ValueError("malformed_command")

    @field_validator("request_id", "evidence_target")
    @classmethod
    def _validate_text(cls, value: str | None) -> str | None:
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
    def __init__(self, policy: SandboxPolicy | None = None) -> None:
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
    request: TerminalDispatchRequest | str | Sequence[str],
    *,
    root: Path | None = None,
    evidence_target: str | None = None,
) -> TerminalDispatchResult:
    match request:
        case TerminalDispatchRequest():
            dispatch_request = request
        case str():
            dispatch_request = TerminalDispatchRequest(
                command=request,
                root=root,
                evidence_target=evidence_target,
            )
        case _:
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


def _command_text(command: str | tuple[str, ...]) -> str:
    match command:
        case str():
            return command
        case tuple():
            return " ".join(command)
        case unreachable:
            assert_never(unreachable)


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
