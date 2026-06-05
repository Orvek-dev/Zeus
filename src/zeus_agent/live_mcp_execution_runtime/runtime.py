from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_execution_readiness_runtime import LiveExecutionReadinessResult
from zeus_agent.security.credentials import redact_secret_spans

LiveMcpExecutionDecision = Literal["selected", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_ALLOWED_TOOLS: Final = {"mcp.echo"}
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=sk",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


class LiveMcpExecutionResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveMcpExecutionDecision
    tool_name: str
    output: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    tool_invoked: bool = False
    server_started: bool = False
    resources_enabled: bool = False
    prompts_enabled: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveMcpExecutionRuntime:
    def invoke(
        self,
        *,
        readiness: Optional[LiveExecutionReadinessResult],
        tool_name: str,
        arguments: dict[str, JsonValue],
    ) -> LiveMcpExecutionResult:
        safe_tool_name = redact_secret_spans(tool_name.strip())
        reasons = list(_readiness_reasons(readiness))
        if safe_tool_name not in _ALLOWED_TOOLS:
            reasons.append("unsupported_mcp_tool")
        if reasons:
            return _result(
                decision="blocked",
                tool_name=safe_tool_name,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        return _result(
            decision="selected",
            tool_name=safe_tool_name,
            output={"text": _safe_text(arguments.get("text"))},
            tool_invoked=True,
        )


def _readiness_reasons(readiness: Optional[LiveExecutionReadinessResult]) -> tuple[str, ...]:
    if readiness is None:
        return ("execution_readiness_required",)
    reasons = []
    if readiness.decision != "ready_for_external_operator":
        reasons.append("execution_readiness_not_ready")
    if readiness.surface_kind != "mcp":
        reasons.append("readiness_surface_not_mcp")
    if readiness.execution_allowed or readiness.authority_granted or readiness.live_transport_enabled:
        reasons.append("readiness_authority_forbidden")
    if readiness.network_opened or readiness.handler_executed or readiness.external_delivery_opened:
        reasons.append("readiness_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return redact_secret_spans(str(value))


def _result(
    *,
    decision: LiveMcpExecutionDecision,
    tool_name: str,
    output: Optional[dict[str, JsonValue]] = None,
    blocked_reasons: tuple[str, ...] = (),
    tool_invoked: bool = False,
) -> LiveMcpExecutionResult:
    result = LiveMcpExecutionResult(
        decision=decision,
        tool_name=tool_name,
        output=output,
        blocked_reasons=blocked_reasons,
        tool_invoked=tool_invoked,
        server_started=False,
        resources_enabled=False,
        prompts_enabled=False,
        execution_allowed=False,
        authority_granted=False,
        live_transport_enabled=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveMcpExecutionResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
