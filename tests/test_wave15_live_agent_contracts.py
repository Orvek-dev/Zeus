from __future__ import annotations

from zeus_agent.live_agent_loop import LiveAgentLoopRequest


def test_live_agent_loop_contract_binds_objective_lease_and_evidence() -> None:
    raw_secret = "sk-wave15-contract-secret"

    request = LiveAgentLoopRequest(
        request_id="g001.req.local",
        objective_id="g001.objective.liveagent",
        message="use token {0}".format(raw_secret),
        evidence_target="mneme.wave15.live_agent",
        provider_kind="fake",
    )

    serialized = request.model_dump_json()
    assert request.objective_id == "g001.objective.liveagent"
    assert request.evidence_target == "mneme.wave15.live_agent"
    assert request.provider_kind == "fake"
    assert raw_secret not in serialized
    assert "sk-...redacted" in serialized
