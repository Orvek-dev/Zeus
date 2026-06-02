from __future__ import annotations

from pathlib import Path
from typing import Any

from zeus_agent.kernel.authority import AuthorityContext, CapabilityGrant, PathGrant
from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityRisk,
    SideEffect,
)
from zeus_agent.kernel.completion import AcceptanceEvidence, map_acceptance_evidence
from zeus_agent.kernel.contracts import ExecutionMode, ExecutionSpec, GoalContract
from zeus_agent.kernel.evidence import EvidenceStatus, MnemeEvidenceRecord
from zeus_agent.model_runtime import (
    FakeModelRuntime,
    ModelRequest,
    ModelResponse,
    ToolCall,
)
from zeus_agent.model_runtime.fake import fake_tool_matrix
from zeus_agent.state import SQLiteStateStore

CRITERION_ID = "REQ-ZEUS-WAVE2-001:S1"
PROFILE = "coding-agent"


def run_wave2_loop(scenario: str, home: Path) -> dict[str, Any]:
    if scenario not in {"happy", "blocked"}:
        raise ValueError("scenario must be one of: happy, blocked")

    store = SQLiteStateStore(home / "wave2-state.sqlite3")
    contract = _contract()
    execution = _execution(contract)
    authority = _authority()
    graph = _graph()
    marker = {"file_read": False, "terminal_run": False}
    broker = CapabilityBroker(graph=graph, handlers=_handlers(marker))
    visible_schema = graph.compile_model_schema(profile=PROFILE, authority=authority)
    visible_tools = [entry["function"]["name"] for entry in visible_schema]
    prompt_context = _prompt_context(contract, execution, visible_tools)
    runtime = _runtime_for(scenario)
    session_id = "wave2-session-{0}".format(scenario)

    store.create_session(session_id, execution.run_id, contract.goal_contract_id)
    request = ModelRequest(
        prompt_context=prompt_context,
        tool_schema=visible_schema,
    )
    first_turn = runtime.next_response(request)
    store.add_model_turn(first_turn.turn_id, session_id, "assistant", first_turn.content)
    tool_call = first_turn.tool_call
    if tool_call is None:
        raise ValueError("fake Wave 2 scenario must include one tool call")

    dispatch = broker.dispatch(
        capability_id=tool_call.capability_id,
        payload=tool_call.arguments,
        context=authority,
        profile=PROFILE,
        criterion_id=CRITERION_ID,
    )
    handler_executed = marker["file_read"] or marker["terminal_run"]
    broker_record = MnemeEvidenceRecord.model_validate(dispatch["evidence"])
    broker_evidence_id = "evidence-{0}".format(tool_call.tool_call_id)
    store.add_evidence(broker_evidence_id, broker_record)
    store.add_tool_call(
        tool_call.tool_call_id,
        first_turn.turn_id,
        tool_call.capability_id,
        tool_call.arguments,
        str(dispatch["decision"]),
        handler_executed,
        broker_evidence_id,
    )

    acceptance = map_acceptance_evidence(contract, broker.evidence_records)
    completion_record = _completion_record(execution, contract, acceptance)
    completion_evidence_id = "evidence-acceptance-{0}".format(scenario)
    store.add_evidence(completion_evidence_id, completion_record)
    if acceptance.status == "complete":
        store.add_acceptance_link(CRITERION_ID, broker_evidence_id, "verified")
        final_turn = runtime.next_response(request)
        store.add_model_turn(final_turn.turn_id, session_id, "assistant", final_turn.content)
        model_turn = final_turn
    else:
        model_turn = first_turn

    return {
        "scenario": scenario,
        "session_id": session_id,
        "state_db": str(store.db_path),
        "model_turn": _model_turn_payload(model_turn),
        "tool_call": tool_call.model_dump(mode="json"),
        "broker_decision": _broker_decision(dispatch),
        "handler_executed": handler_executed,
        "acceptance_evidence": acceptance.model_dump(mode="json"),
        "state_counts": store.counts().model_dump(mode="json"),
        "prompt_context": prompt_context,
        "provider_matrix": runtime.matrix.model_dump(mode="json"),
    }


def _contract() -> GoalContract:
    return GoalContract(
        goal_contract_id="wave2-goal",
        raw_user_request="run fake Wave 2 loop",
        normalized_goal="persist fake model tool call evidence",
        deliverables=["fake local loop"],
        acceptance_criteria=[CRITERION_ID],
    )


def _execution(contract: GoalContract) -> ExecutionSpec:
    return ExecutionSpec(
        run_id="wave2-run",
        goal_contract_id=contract.goal_contract_id,
        execution_mode=ExecutionMode.AUTHORIZED_DISPATCH,
    )


def _authority() -> AuthorityContext:
    return AuthorityContext(
        principal_id="wave2-principal",
        run_id="wave2-run",
        goal_contract_id="wave2-goal",
        capability_grants=[CapabilityGrant(capability_id="file.read")],
        path_grants=[PathGrant(capability_id="file.read", path_prefix="/virtual/")],
    )


def _graph() -> CapabilityGraph:
    return CapabilityGraph(
        [
            CapabilityDescriptor(
                capability_id="file.read",
                name="file.read",
                risk=CapabilityRisk.low,
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                output_schema={"type": "object"},
            ),
            CapabilityDescriptor(
                capability_id="terminal.run",
                name="terminal.run",
                risk=CapabilityRisk.high,
                input_schema={"type": "object", "properties": {"cmd": {"type": "string"}}},
                output_schema={"type": "object"},
                side_effects=[SideEffect.local_process],
            ),
        ]
    )


def _handlers(marker: dict[str, bool]) -> dict[str, Any]:
    def read_handler(payload: dict[str, object]) -> dict[str, object]:
        marker["file_read"] = True
        return {"path": payload.get("path"), "content": "wave2 fixture content"}

    def terminal_handler(payload: dict[str, object]) -> dict[str, object]:
        marker["terminal_run"] = True
        return {"accepted": bool(payload)}

    return {"file.read": read_handler, "terminal.run": terminal_handler}


def _prompt_context(
    contract: GoalContract,
    execution: ExecutionSpec,
    visible_tools: list[str],
) -> dict[str, str | list[str]]:
    from .prompt import build_prompt_context

    return build_prompt_context(contract, execution, visible_tools, PROFILE).model_dump(mode="json")


def _runtime_for(scenario: str) -> FakeModelRuntime:
    tool_call = ToolCall(
        tool_call_id="tool-call-{0}-1".format(scenario),
        capability_id="file.read" if scenario == "happy" else "terminal.run",
        arguments={"path": "/virtual/wave2.txt"} if scenario == "happy" else {"cmd": "echo blocked"},
    )
    return FakeModelRuntime(
        matrix=fake_tool_matrix(),
        responses=[
            ModelResponse(turn_id="turn-1-tool", content="requesting brokered tool", tool_call=tool_call),
            ModelResponse(turn_id="turn-2-final", content="acceptance evidence complete"),
        ],
    )


def _completion_record(
    execution: ExecutionSpec,
    contract: GoalContract,
    acceptance: AcceptanceEvidence,
) -> MnemeEvidenceRecord:
    status = EvidenceStatus.PASS if acceptance.status == "complete" else EvidenceStatus.BLOCKED
    return MnemeEvidenceRecord(
        run_id=execution.run_id,
        goal_contract_id=contract.goal_contract_id,
        criterion_id=CRITERION_ID,
        evidence_type="acceptance_mapping",
        summary="acceptance_status={0}".format(acceptance.status),
        status=status,
    )


def _model_turn_payload(turn: ModelResponse) -> dict[str, str | None]:
    return {
        "turn_id": turn.turn_id,
        "content": turn.content,
        "tool_call_id": turn.tool_call.tool_call_id if turn.tool_call is not None else None,
    }


def _broker_decision(dispatch: dict[str, Any]) -> dict[str, str]:
    payload = {
        "decision": str(dispatch["decision"]),
        "capability_id": str(dispatch["capability_id"]),
    }
    reason = dispatch.get("reason")
    if reason is not None:
        payload["reason"] = str(reason)
    return payload
