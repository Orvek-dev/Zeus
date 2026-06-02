from __future__ import annotations

import pytest

from zeus_agent.kernel.authority import ApprovalReceipt, AuthorityContext, CapabilityGrant
from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityHealth,
    CapabilityRisk,
    SideEffect,
)


def _authority(capability_ids: list[str]) -> AuthorityContext:
    return AuthorityContext(
        principal_id="principal-a",
        run_id="run-1",
        goal_contract_id="goal-1",
        capability_grants=[CapabilityGrant(capability_id=value) for value in capability_ids],
    )


def test_schema_compiler_intersects_profile_authority_health_and_risk() -> None:
    authority = _authority(
        [
            "file.read",
            "terminal.run",
            "network.fetch",
            "legacy.search",
            "ops.admin",
        ]
    )
    approvals = [
        ApprovalReceipt(
            principal_id="principal-a",
            run_id="run-1",
            goal_contract_id="goal-1",
            approved_capabilities=["terminal.run", "network.fetch"],
        )
    ]
    graph = CapabilityGraph(
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
            CapabilityDescriptor(
                capability_id="network.fetch",
                name="network.fetch",
                risk=CapabilityRisk.low,
                input_schema={"type": "object", "properties": {"url": {"type": "string"}}},
                output_schema={"type": "object"},
                side_effects=[SideEffect.network],
            ),
            CapabilityDescriptor(
                capability_id="legacy.search",
                name="legacy.search",
                risk=CapabilityRisk.low,
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object"},
                health=CapabilityHealth.unhealthy,
            ),
            CapabilityDescriptor(
                capability_id="ops.admin",
                name="ops.admin",
                risk=CapabilityRisk.low,
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object"},
                profiles=["ops"],
            ),
            CapabilityDescriptor(
                capability_id="file.write",
                name="file.write",
                risk=CapabilityRisk.low,
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object"},
                side_effects=[SideEffect.filesystem_write],
            ),
        ]
    )

    visible = graph.compile_model_schema(
        profile="worker",
        authority=authority,
        approval_receipts=approvals,
    )
    assert [entry["function"]["name"] for entry in visible] == [
        "file.read",
        "terminal.run",
        "network.fetch",
    ]

    hidden_without_approvals = graph.compile_model_schema(profile="worker", authority=authority)
    assert [entry["function"]["name"] for entry in hidden_without_approvals] == ["file.read"]

    with_unhealthy = graph.compile_model_schema(
        profile="worker",
        authority=authority,
        approval_receipts=approvals,
        include_unhealthy=True,
    )
    assert [entry["function"]["name"] for entry in with_unhealthy] == [
        "file.read",
        "terminal.run",
        "network.fetch",
        "legacy.search",
    ]

    with pytest.raises(ValueError, match="file.read"):
        CapabilityGraph(
            [
                CapabilityDescriptor(
                    capability_id="file.read",
                    name="file.read",
                    risk=CapabilityRisk.low,
                    input_schema={"type": "object", "properties": {}},
                    output_schema={"type": "object"},
                ),
                CapabilityDescriptor(
                    capability_id="file.read",
                    name="file.read.duplicate",
                    risk=CapabilityRisk.low,
                    input_schema={"type": "object", "properties": {}},
                    output_schema={"type": "object"},
                ),
            ]
        )


def test_dangerous_capability_is_hidden_when_unapproved() -> None:
    authority = _authority(["terminal.run", "db.write"])
    graph = CapabilityGraph(
        [
            CapabilityDescriptor(
                capability_id="terminal.run",
                name="terminal.run",
                risk=CapabilityRisk.high,
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object"},
            ),
            CapabilityDescriptor(
                capability_id="db.write",
                name="db.write",
                risk=CapabilityRisk.low,
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "object"},
                side_effects=[SideEffect.filesystem_write],
            ),
        ]
    )

    visible = graph.compile_model_schema(profile="worker", authority=authority, approval_receipts=[])
    assert visible == []


def test_graph_rejects_duplicate_descriptor_name_when_ids_differ() -> None:
    with pytest.raises(ValueError, match="duplicate name: shared.capability"):
        CapabilityGraph(
            [
                CapabilityDescriptor(
                    capability_id="capability.one",
                    name="shared.capability",
                    risk=CapabilityRisk.low,
                    input_schema={"type": "object", "properties": {}},
                    output_schema={"type": "object"},
                ),
                CapabilityDescriptor(
                    capability_id="capability.two",
                    name="shared.capability",
                    risk=CapabilityRisk.low,
                    input_schema={"type": "object", "properties": {}},
                    output_schema={"type": "object"},
                ),
            ]
        )
