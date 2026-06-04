from __future__ import annotations

from pathlib import Path
from typing import Literal

from zeus_agent.kernel.evidence import MnemeEvidenceRecord
from zeus_agent.live_agent_loop.tools import build_local_echo_tool_runtime
from zeus_agent.model_runtime.interfaces import ProviderRuntimeKind
from zeus_agent.model_runtime.provider_registry import EVIDENCE_TARGET as PROVIDER_EVIDENCE_TARGET, ProviderRegistry
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.security.credentials import redact_secret_spans
from zeus_agent.tool_runtime import ToolExecutionRequest, ToolRuntimeRegistry
from zeus_agent.agent_runtime.live_loop_models import LiveAgentLoopResult, RetryPolicy
from zeus_agent.agent_runtime.live_loop_resilience import generate_provider_seed, retry_limit_reached
from zeus_agent.agent_runtime.live_loop_store import LiveAgentLoopPersistence
from zeus_agent.agent_runtime.live_loop_support import CAPABILITY_ID, EXPIRES, NOW, TOOL_EVIDENCE_TARGET, TOOL_NAME
from zeus_agent.agent_runtime.live_loop_support import MAX_ECHO_TEXT_LENGTH
from zeus_agent.agent_runtime.live_loop_support import blocked_result, has_injection_marker, no_secret_echo
from zeus_agent.agent_runtime.live_loop_support import provider_followup_request, provider_reason, provider_request, scripted_final_turn
from zeus_agent.agent_runtime.live_loop_support import scripted_tool_turn, stream_chunks, tool_feedback, tool_reason
from zeus_agent.agent_runtime.live_loop_support import verification_allowed


class LiveAgentLoop:
    def __init__(self, home: Path, provider_registry: ProviderRegistry | None = None) -> None:
        self._provider_registry = provider_registry or ProviderRegistry()
        self._persistence = LiveAgentLoopPersistence(home)

    def run_tool_loop(
        self,
        message: str,
        provider_lease: RuntimeLease | None,
        tool_lease: RuntimeLease | None,
        *,
        tool_name: str = TOOL_NAME,
        retry_policy: RetryPolicy | None = None,
        cancellation_requested: bool = False,
        fallback_provider_kind: ProviderRuntimeKind | None = None,
        fallback_provider_lease: RuntimeLease | None = None,
    ) -> LiveAgentLoopResult:
        normalized = redact_secret_spans(message.strip())
        if cancellation_requested:
            return self._blocked_with_audit("cancellation_recorded", normalized)
        if normalized == "":
            return self._blocked_with_audit("empty_message", normalized)
        if len(normalized) > MAX_ECHO_TEXT_LENGTH:
            return self._blocked_with_audit("message_too_large", "len={0}".format(len(normalized)))
        if has_injection_marker(normalized):
            return self._blocked_with_audit("unsafe_context_injection", normalized)

        tool_runtime = self._tool_runtime()
        request = provider_request(normalized, stream=True)
        first_dispatch = generate_provider_seed(
            provider_registry=self._provider_registry,
            persistence=self._persistence,
            request=request,
            lease=provider_lease,
            retry_policy=retry_policy,
            fallback_provider_kind=fallback_provider_kind,
            fallback_provider_lease=fallback_provider_lease,
        )
        first_seed = first_dispatch.response
        provider_attempts = first_dispatch.attempts
        if first_seed.decision == "blocked":
            reason = provider_reason(first_seed)
            audit_message = normalized
            if retry_limit_reached(retry_policy, provider_attempts):
                reason = "retry_limit_enforced"
                audit_message = "{0} attempts={1} last_reason={2}".format(
                    normalized,
                    provider_attempts,
                    provider_reason(first_seed),
                )
            return self._blocked_with_audit(
                reason,
                audit_message,
                network_opened=first_seed.network_opened,
                provider_turns=provider_attempts,
            )

        first_turn = scripted_tool_turn(first_seed, normalized, tool_name)
        tool_call = first_turn.tool_calls[0]
        tool_result = tool_runtime.execute(
            ToolExecutionRequest(
                tool_name=tool_call.tool_name,
                arguments=tool_call.arguments_as_dict(),
                tool_call_id=tool_call.call_id,
            ),
            tool_lease,
            now=NOW,
        )
        if tool_result.decision != "allowed" or tool_result.evidence is None:
            return self._blocked_with_audit(
                tool_reason(tool_result.reason),
                normalized,
                network_opened=first_seed.network_opened
                or first_turn.network_opened
                or tool_result.network_opened,
                provider_decision="selected",
                provider_turns=provider_attempts,
                handler_executed=tool_result.handler_executed,
            )

        final_dispatch = generate_provider_seed(
            provider_registry=self._provider_registry,
            persistence=self._persistence,
            request=provider_followup_request(
                first_dispatch.selected_request,
                tool_feedback(tool_result.model_dump_json()),
                stream=False,
            ),
            lease=first_dispatch.selected_lease,
            retry_policy=retry_policy,
            fallback_provider_kind=None if first_dispatch.fallback_used else fallback_provider_kind,
            fallback_provider_lease=None if first_dispatch.fallback_used else fallback_provider_lease,
        )
        final_seed = final_dispatch.response
        provider_attempts += final_dispatch.attempts
        if final_seed.decision == "blocked":
            network_opened = first_seed.network_opened or first_turn.network_opened or tool_result.network_opened or final_seed.network_opened
            reason = provider_reason(final_seed)
            audit_message = normalized
            if retry_limit_reached(retry_policy, final_dispatch.attempts):
                reason = "retry_limit_enforced"
                audit_message = "{0} attempts={1} last_reason={2}".format(
                    normalized,
                    provider_attempts,
                    provider_reason(final_seed),
                )
            return self._blocked_with_audit(
                reason,
                audit_message,
                network_opened=network_opened,
                provider_decision="selected",
                provider_turns=provider_attempts,
                handler_executed=tool_result.handler_executed,
            )
        final_turn = scripted_final_turn(final_seed, tool_call.call_id)
        evidence_delta, session_persisted, audit_events, audit_record_created = self._persistence.persist_session(
            message=normalized,
            first_turn=first_turn,
            tool_result_json=tool_result.model_dump_json(),
            tool_evidence=MnemeEvidenceRecord.model_validate(tool_result.evidence),
            final_turn=final_turn,
        )
        network_opened = (
            first_seed.network_opened
            or first_turn.network_opened
            or tool_result.network_opened
            or final_seed.network_opened
            or final_turn.network_opened
        )
        secret_safe = no_secret_echo(
            first_turn.model_dump_json(),
            tool_result.model_dump_json(),
            final_turn.model_dump_json(),
        )
        return LiveAgentLoopResult(
            decision="selected",
            provider_decision="selected",
            provider_turns=provider_attempts,
            streaming_chunks_recorded=len(stream_chunks(first_turn.content)) >= 2,
            tool_calls_processed=1,
            tool_result_recorded=True,
            evidence_records=evidence_delta,
            audit_events=audit_events,
            audit_record_created=audit_record_created,
            session_persisted=session_persisted,
            verification_completion_allowed=verification_allowed(evidence_delta >= 2),
            handler_executed=tool_result.handler_executed,
            network_opened=network_opened,
            no_secret_echo=secret_safe,
        )

    def malformed_tool_call_result(self) -> LiveAgentLoopResult:
        result = self._tool_runtime().inspect_untrusted_call(
            {"name": TOOL_NAME, "arguments": "{not-json", "id": "wave15.call.bad"},
            self.tool_lease(),
            now=NOW,
        )
        if result.decision == "blocked":
            return self._blocked_with_audit("malformed_tool_call", "malformed tool call")
        return blocked_result("malformed_tool_call_not_blocked")

    def audit_event_count(self) -> int:
        return self._persistence.audit_event_count()

    def provider_lease(self) -> RuntimeLease:
        return RuntimeLease(
            lease_id="wave15.lease.provider",
            objective_id="wave15.objective.liveagent",
            principal_id="wave15.principal.agent",
            run_id="wave15.run.provider",
            allowed_capabilities=("provider.fake.generate",),
            budget_limit=100,
            evidence_target=PROVIDER_EVIDENCE_TARGET,
            issued_at=NOW,
            expires_at=EXPIRES,
        )

    def tool_lease(self) -> RuntimeLease:
        return RuntimeLease(
            lease_id="wave15.lease.tool",
            objective_id="wave15.objective.liveagent",
            principal_id="wave15.principal.agent",
            run_id="wave15.run.tool",
            allowed_capabilities=(CAPABILITY_ID,),
            budget_limit=100,
            evidence_target=TOOL_EVIDENCE_TARGET,
            issued_at=NOW,
            expires_at=EXPIRES,
        )

    def _tool_runtime(self) -> ToolRuntimeRegistry:
        return build_local_echo_tool_runtime()

    def _blocked_with_audit(
        self,
        reason: str,
        message: str,
        *,
        network_opened: bool = False,
        provider_decision: Literal["selected", "blocked"] = "blocked",
        provider_turns: int = 0,
        handler_executed: bool = False,
    ) -> LiveAgentLoopResult:
        result = blocked_result(
            reason,
            network_opened,
            provider_decision=provider_decision,
            provider_turns=provider_turns,
            handler_executed=handler_executed,
        )
        audit_delta = self._persistence.persist_deny_audit(
            reason=reason,
            message=message,
            network_opened=network_opened,
            handler_executed=handler_executed,
        )
        return result.model_copy(
            update={"audit_events": audit_delta, "audit_record_created": audit_delta >= 1},
        )
