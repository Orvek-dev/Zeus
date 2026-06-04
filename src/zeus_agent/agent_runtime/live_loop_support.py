from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Final, Literal, Optional
from uuid import uuid4

from zeus_agent.agent_runtime.live_loop_models import LiveAgentLoopResult
from zeus_agent.kernel.evidence import EvidenceStatus, MnemeEvidenceRecord
from zeus_agent.model_runtime.interfaces import (
    ProviderMessage,
    ProviderRuntimeResponse,
    ProviderRuntimeRequest,
    ProviderToolCall,
    ProviderToolDefinition,
    ProviderToolResult,
    ProviderUsage,
)
from zeus_agent.security.credentials import redact_secret_spans
from zeus_agent.verification_runtime.engine import (
    VerificationEngine,
    VerificationObligation,
)
from zeus_agent.workloop_runtime import OrchestrationLane, build_work_loop_plan

NOW: Final = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
EXPIRES: Final = datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc)
TOOL_EVIDENCE_TARGET: Final = "mneme.wave15.live_agent"
TOOL_NAME: Final = "local.echo"
CAPABILITY_ID: Final = "api.tool.echo"
MAX_ECHO_TEXT_LENGTH: Final = 4096
INJECTION_MARKERS: Final = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "developer message",
    "reveal secret",
    "exfiltrate",
)


def provider_request(message: str, *, stream: bool) -> ProviderRuntimeRequest:
    return ProviderRuntimeRequest(
        provider_kind="fake",
        provider_id="fake.wave15",
        model_id="fake.wave15.local",
        messages=(ProviderMessage(role="user", content=message),),
        tools=(
            ProviderToolDefinition(
                name=TOOL_NAME,
                description="Local Wave15 evidence tool",
                input_schema={
                    "type": "object",
                    "text_max_length": MAX_ECHO_TEXT_LENGTH,
                },
            ),
        ),
        stream=stream,
    )


def provider_followup_request(
    request: ProviderRuntimeRequest,
    message: str,
    *,
    stream: bool,
) -> ProviderRuntimeRequest:
    return request.model_copy(
        update={
            "messages": (ProviderMessage(role="user", content=message),),
            "tools": (),
            "stream": stream,
        },
    )


def scripted_tool_turn(
    seed: ProviderRuntimeResponse,
    message: str,
    tool_name: str,
) -> ProviderRuntimeResponse:
    call_id = "wave15.call.{0}".format(uuid4().hex)
    return ProviderRuntimeResponse(
        decision="selected",
        provider_kind=seed.provider_kind,
        provider_id=seed.provider_id,
        model_id=seed.model_id,
        response_id="wave15.provider.turn1",
        content="stream:start|tool-call|stream:end",
        tool_calls=(
            ProviderToolCall(
                call_id=call_id,
                tool_name=tool_name,
                arguments_json=json.dumps({"text": message}, sort_keys=True),
            ),
        ),
        stop_reason="tool_calls",
        usage=ProviderUsage(input_tokens=12, output_tokens=6, budget_units=1, latency_ms=0),
    )


def scripted_final_turn(
    seed: ProviderRuntimeResponse,
    call_id: str,
) -> ProviderRuntimeResponse:
    return ProviderRuntimeResponse(
        decision="selected",
        provider_kind=seed.provider_kind,
        provider_id=seed.provider_id,
        model_id=seed.model_id,
        response_id="wave15.provider.turn2",
        content="local evidence recorded for {0}".format(call_id),
        tool_results=(ProviderToolResult(call_id=call_id, output="recorded"),),
        stop_reason="complete",
        usage=ProviderUsage(input_tokens=8, output_tokens=5, budget_units=1, latency_ms=0),
    )


def blocked_result(
    reason: str,
    network_opened: bool = False,
    *,
    provider_decision: Literal["selected", "blocked"] = "blocked",
    provider_turns: int = 0,
    handler_executed: bool = False,
) -> LiveAgentLoopResult:
    return LiveAgentLoopResult(
        decision="blocked",
        blocked_reasons=(reason,),
        provider_decision=provider_decision,
        provider_turns=provider_turns,
        streaming_chunks_recorded=False,
        tool_calls_processed=0,
        tool_result_recorded=False,
        evidence_records=0,
        audit_events=0,
        audit_record_created=False,
        session_persisted=False,
        verification_completion_allowed=False,
        handler_executed=handler_executed,
        network_opened=network_opened,
        no_secret_echo=True,
    )


def provider_reason(response: ProviderRuntimeResponse) -> str:
    reason = response.metadata_value("block.reason")
    if reason == "missing_runtime_lease":
        return "missing_provider_lease"
    if isinstance(reason, str):
        return reason
    return "provider_blocked"


def tool_reason(reason: Optional[str]) -> str:
    if reason == "missing_runtime_lease":
        return "missing_tool_lease"
    if reason is None:
        return "tool_blocked"
    return reason


def tool_feedback(tool_result_json: str) -> str:
    return "tool result: {0}".format(redact_secret_spans(tool_result_json))


def audit_summary(
    *,
    message: str,
    provider_id: str,
    model_id: str,
    tool_call_id: str,
    tool_name: str,
) -> str:
    return redact_secret_spans(
        json.dumps(
            {
                "event": "wave15.live_agent.dispatch",
                "provider_id": provider_id,
                "model_id": model_id,
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "capability_id": CAPABILITY_ID,
                "message": message,
                "handler_executed": True,
                "network_opened": False,
            },
            sort_keys=True,
        ),
    )


def deny_audit_summary(
    *,
    reason: str,
    message: str,
    network_opened: bool,
    handler_executed: bool = False,
) -> str:
    return redact_secret_spans(
        json.dumps(
            {
                "event": "wave15.live_agent.deny",
                "reason": reason,
                "message": message,
                "handler_executed": handler_executed,
                "network_opened": network_opened,
            },
            sort_keys=True,
        ),
    )


def stream_chunks(content: str) -> tuple[str, ...]:
    return tuple(chunk for chunk in content.split("|") if chunk)


def stream_evidence() -> MnemeEvidenceRecord:
    return MnemeEvidenceRecord(
        run_id="wave15.run.provider",
        goal_contract_id="wave15.objective.liveagent",
        criterion_id="REQ-ZEUS-WAVE15-001:S1",
        evidence_type="provider_stream_chunks",
        summary="streaming_chunks_recorded=true",
        status=EvidenceStatus.PASS,
        capability_id="provider.fake.generate",
    )


def verification_allowed(evidence_present: bool) -> bool:
    target: Optional[str] = "main-orchestrator-script-pty" if evidence_present else None
    plan = build_work_loop_plan(
        goal_contract_id="wave15.liveagent",
        normalized_goal="Run a governed fake/local live agent loop.",
        deliverables=("live-agent-loop",),
        acceptance_criteria=("REQ-ZEUS-WAVE15-001:S1",),
        lanes=(
            OrchestrationLane(
                lane_id="wave15-runtime",
                owned_paths=("src/zeus_agent/agent_runtime/live_loop.py",),
                stop_condition="provider tool result and evidence persisted",
                manual_qa_channel="cli_stdout",
                evidence_target=target,
            ),
        ),
        verification_obligations_count=1,
    )
    summary = VerificationEngine().evaluate(
        plan,
        (
            VerificationObligation(
                obligation_id="wave15-obligation-live-agent",
                requirement_id="REQ-ZEUS-WAVE15-001:S1",
                lane_id="wave15-runtime",
                obligation_type="runtime",
                evidence_target=target,
                evidence_status="passed" if evidence_present else "missing",
            ),
        ),
    )
    return summary.completion_allowed


def has_injection_marker(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in INJECTION_MARKERS)


def no_secret_echo(*payloads: str) -> bool:
    normalized = tuple(payload.replace("no_secret_echo", "redaction_flag") for payload in payloads)
    return all(redact_secret_spans(payload) == payload for payload in normalized)
