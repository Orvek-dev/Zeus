from __future__ import annotations

from zeus_agent.kernel.authority import AuthorityContext, CapabilityGrant, PathGrant
from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityRisk,
    SideEffect,
)


def _authority(capability_ids: list[str], *, path_prefixes: list[str] | None = None) -> AuthorityContext:
    path_grants = [] if path_prefixes is None else [
        PathGrant(capability_id="file.read", path_prefix=value) for value in path_prefixes
    ]
    return AuthorityContext(
        principal_id="principal-1",
        run_id="run-1",
        goal_contract_id="goal-1",
        capability_grants=[CapabilityGrant(capability_id=value) for value in capability_ids],
        path_grants=path_grants,
    )


def _graph() -> CapabilityGraph:
    return CapabilityGraph(
        [
            CapabilityDescriptor(
                capability_id="file.read",
                name="file.read",
                risk=CapabilityRisk.low,
                input_schema={"type": "object", "properties": {}},
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


def test_broker_blocks_unapproved_mutating_capability_before_handler() -> None:
    graph = _graph()
    authority = _authority(["terminal.run"])
    handler_called = {"count": 0}

    def terminal_handler(payload: dict[str, object]) -> dict[str, object]:
        handler_called["count"] += 1
        return {"ok": True, "payload": payload}

    broker = CapabilityBroker(graph=graph, handlers={"terminal.run": terminal_handler})
    response = broker.dispatch(
        capability_id="terminal.run",
        payload={"cmd": "echo hello"},
        context=authority,
    )

    assert response["decision"] == "blocked"
    assert response["capability_id"] == "terminal.run"
    assert handler_called["count"] == 0
    assert response["reason"] == "capability_not_model_visible"
    assert response["evidence"]["status"] == "blocked"
    assert len(broker.evidence_records) == 1
    assert broker.evidence_records[0].status.value == "blocked"
    assert broker.evidence_records[0].criterion_id == "REQ-ZEUS-KERNEL-006:S1"


def test_broker_records_mneme_evidence_for_allowed_capability() -> None:
    graph = _graph()
    authority = _authority(["file.read"], path_prefixes=["/virtual/"])

    def read_handler(payload: dict[str, object]) -> dict[str, object]:
        return {"echo": payload.get("path"), "result": "ok"}

    broker = CapabilityBroker(graph=graph, handlers={"file.read": read_handler})
    response = broker.dispatch(
        capability_id="file.read",
        payload={"path": "/virtual/path.txt"},
        context=authority,
    )

    assert response["decision"] == "allowed"
    assert response["capability_id"] == "file.read"
    assert response["result"] == {"echo": "/virtual/path.txt", "result": "ok"}
    assert response["evidence"]["status"] == "pass"
    assert len(broker.evidence_records) == 1

    evidence = broker.evidence_records[0]
    assert evidence.run_id == "run-1"
    assert evidence.goal_contract_id == "goal-1"
    assert evidence.criterion_id == "REQ-ZEUS-KERNEL-006:S1"
    assert evidence.capability_id == "file.read"
    assert evidence.status.value == "pass"


def test_broker_blocks_file_read_without_matching_path_scope_before_handler() -> None:
    graph = _graph()
    authority = _authority(["file.read"])
    handler_called = {"count": 0}

    def read_handler(payload: dict[str, object]) -> dict[str, object]:
        handler_called["count"] += 1
        return {"echo": payload.get("path"), "result": "ok"}

    broker = CapabilityBroker(graph=graph, handlers={"file.read": read_handler})
    response = broker.dispatch(
        capability_id="file.read",
        payload={"path": "/outside.txt"},
        context=authority,
    )

    assert response["decision"] == "blocked"
    assert response["reason"] == "path_scope_missing"
    assert response["capability_id"] == "file.read"
    assert handler_called["count"] == 0


def test_broker_ignores_untrusted_payload_criterion_id_for_evidence() -> None:
    graph = _graph()
    authority = _authority(["file.read"], path_prefixes=["/virtual/"])

    def read_handler(payload: dict[str, object]) -> dict[str, object]:
        return {"echo": payload.get("path"), "result": "ok"}

    broker = CapabilityBroker(graph=graph, handlers={"file.read": read_handler})
    response = broker.dispatch(
        capability_id="file.read",
        payload={
            "path": "/virtual/path.txt",
            "criterion_id": "REQ-FAKE-999:S1",
        },
        context=authority,
    )

    assert response["decision"] == "allowed"
    assert response["evidence"]["criterion_id"] == "REQ-ZEUS-KERNEL-006:S1"
    assert broker.evidence_records[0].criterion_id == "REQ-ZEUS-KERNEL-006:S1"


def test_broker_uses_trusted_dispatch_criterion_id_kwarg() -> None:
    graph = _graph()
    authority = _authority(["file.read"], path_prefixes=["/virtual/"])

    def read_handler(payload: dict[str, object]) -> dict[str, object]:
        return {"echo": payload.get("path"), "result": "ok"}

    broker = CapabilityBroker(graph=graph, handlers={"file.read": read_handler})
    response = broker.dispatch(
        capability_id="file.read",
        payload={
            "path": "/virtual/path.txt",
            "criterion_id": "REQ-FAKE-999:S1",
        },
        context=authority,
        criterion_id="REQ-TRUSTED-777:S2",
    )

    assert response["decision"] == "allowed"
    assert response["evidence"]["criterion_id"] == "REQ-TRUSTED-777:S2"
    assert broker.evidence_records[0].criterion_id == "REQ-TRUSTED-777:S2"


def test_broker_falls_back_to_default_for_invalid_trusted_criterion_id_kwarg() -> None:
    graph = _graph()
    authority = _authority(["file.read"], path_prefixes=["/virtual/"])

    def read_handler(payload: dict[str, object]) -> dict[str, object]:
        return {"echo": payload.get("path"), "result": "ok"}

    broker = CapabilityBroker(graph=graph, handlers={"file.read": read_handler})
    response = broker.dispatch(
        capability_id="file.read",
        payload={"path": "/virtual/path.txt"},
        context=authority,
        criterion_id="not-a-req",
    )

    assert response["decision"] == "allowed"
    assert response["evidence"]["criterion_id"] == "REQ-ZEUS-KERNEL-006:S1"
    assert broker.evidence_records[0].criterion_id == "REQ-ZEUS-KERNEL-006:S1"
