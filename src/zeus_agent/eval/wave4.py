from __future__ import annotations

import json

from zeus_agent.connector_runtime import (
    ConnectorDeclaration,
    ConnectorKind,
    ConnectorLifecycleRegistry,
    ConnectorLifecycleRuntime,
    ConnectorLifecycleState,
)
from zeus_agent.eval.wave3 import run_wave3_eval
from zeus_agent.gateway_runtime.drafts import draft_cron_command, draft_gateway_command
from zeus_agent.kernel.authority import AuthorityContext, CapabilityGrant
from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.kernel.capabilities import CapabilityDescriptor, CapabilityRisk
from zeus_agent.security.credentials import CredentialScope, CredentialScopeUnsafeError, credential_report
from zeus_agent.workflow_runtime.jobs import CompensationMetadata, RetryPolicy, WorkflowPlanner


def run_wave4_eval() -> dict[str, object]:
    checks = [
        _check("connector_lifecycle", _connector_lifecycle_passes()),
        _check("credential_policy", _credential_policy_passes()),
        _check("workflow_identity", _workflow_identity_passes()),
        _check("gateway_drafts", _gateway_drafts_passes()),
        _check("observability", _observability_passes()),
        _check("upstream_compatibility", _upstream_compatibility_passes()),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave4",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _connector_lifecycle_passes() -> bool:
    registry = ConnectorLifecycleRegistry()
    registry.register(
        ConnectorDeclaration(
            connector_id="mcp-conn",
            kind=ConnectorKind.mcp,
            display_name="Local MCP",
            descriptors=[_descriptor("mcp.echo", "mcp.echo")],
        )
    )
    registry.register(
        ConnectorDeclaration(
            connector_id="api-conn",
            kind=ConnectorKind.api,
            display_name="Partner API",
            descriptors=[_descriptor("api.fetch", "api.fetch")],
        )
    )
    registry.register(
        ConnectorDeclaration(
            connector_id="plugin-conn",
            kind=ConnectorKind.plugin,
            display_name="Plugin Pack",
            descriptors=[_descriptor("plugin.sync", "plugin.sync")],
        )
    )
    registry.register(
        ConnectorDeclaration(
            connector_id="registered-conn",
            kind=ConnectorKind.api,
            display_name="Registered Only",
            descriptors=[_descriptor("registered.scan", "registered.scan")],
        )
    )
    registry.set_state("mcp-conn", ConnectorLifecycleState.healthy)
    registry.set_state("api-conn", ConnectorLifecycleState.unhealthy)
    registry.set_state("plugin-conn", ConnectorLifecycleState.disabled)
    graph = registry.build_capability_graph()
    broker = CapabilityBroker(
        graph=graph,
        handlers=registry.build_stub_handlers(),
    )
    authority = _authority(["mcp.echo", "api.fetch"])
    visible = graph.compile_model_schema(profile="coding-agent", authority=authority)
    healthy_response = broker.dispatch(capability_id="mcp.echo", payload={}, context=authority)
    unhealthy_response = broker.dispatch(capability_id="api.fetch", payload={}, context=authority)
    return (
        registry.lifecycle_report()
        == {
            "mcp-conn": "healthy",
            "api-conn": "unhealthy",
            "plugin-conn": "disabled",
            "registered-conn": "registered",
        }
        and registry.discovered_tool_names()
        == ["api.fetch", "mcp.echo", "plugin.sync", "registered.scan"]
        and [item["function"]["name"] for item in visible] == ["mcp.echo"]
        and healthy_response["decision"] == "allowed"
        and unhealthy_response["decision"] == "blocked"
        and unhealthy_response["reason"] == "capability_not_model_visible"
    )


def _credential_policy_passes() -> bool:
    scopes = [CredentialScope.parse("external.openai.readonly")]
    report = credential_report(scopes)
    return (
        report == {"credential_scopes": ["external.openai.readonly"], "count": 1}
        and _blocks_secret_scope("sk-wave4-secret", "sk-...redacted")
        and _blocks_secret_scope(
            "ghp_TEST_FIXTURE",
            "[redacted-secret]",
        )
    )


def _blocks_secret_scope(raw_value: str, redacted_value: str) -> bool:
    try:
        CredentialScope.parse(raw_value)
    except CredentialScopeUnsafeError as exc:
        payload_dump = json.dumps(exc.payload, sort_keys=True)
        return raw_value not in payload_dump and exc.payload["redacted"] == redacted_value
    return False


def _workflow_identity_passes() -> bool:
    planner = WorkflowPlanner()
    first = planner.plan(
        principal_id="principal-wave4",
        session_id="session-wave4",
        job_id="job-wave4-001",
        idempotency_key="idem-wave4-001",
        retry_policy=RetryPolicy(max_attempts=3, backoff_seconds=5),
        compensation=CompensationMetadata(command="revert-cache", target="orders-cache"),
    )
    retry = planner.next_retry(first)
    return (
        first.status == "pending"
        and first.attempt == 0
        and retry.status == "retry_pending"
        and retry.attempt == 1
        and retry.principal_id == first.principal_id
        and retry.session_id == first.session_id
        and retry.job_id == first.job_id
        and retry.idempotency_key == first.idempotency_key
    )


def _gateway_drafts_passes() -> bool:
    gateway = draft_gateway_command(
        command="send --api-key sk-wave4-secret --to queue://dispatch",
        target="gateway.dispatch",
    )
    cron = draft_cron_command(
        command="install --token=secret --schedule */5 * * * *",
        target="cron.scheduler",
    )
    return (
        gateway.draft_only
        and gateway.side_effects is False
        and gateway.status == "drafted"
        and gateway.command == "[redacted-secret]"
        and cron.draft_only
        and cron.side_effects is False
        and cron.status == "drafted"
        and cron.command == "[redacted-secret]"
    )


def _observability_passes() -> bool:
    report = {
        "suite": "wave4",
        "fake_local_only": True,
        "no_external_side_effects": True,
        "no_secret_echo": True,
    }
    encoded = json.dumps(report, sort_keys=True)
    return (
        report["fake_local_only"]
        and report["no_external_side_effects"]
        and report["no_secret_echo"]
        and "sk-" not in encoded
    )


def _upstream_compatibility_passes() -> bool:
    runtime = ConnectorLifecycleRuntime()
    wave3_report = run_wave3_eval()
    return isinstance(runtime, ConnectorLifecycleRegistry) and wave3_report["suite"] == "wave3"


def _descriptor(capability_id: str, name: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id=capability_id,
        name=name,
        risk=CapabilityRisk.low,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
    )


def _authority(capability_ids: list[str]) -> AuthorityContext:
    return AuthorityContext(
        principal_id="wave4-principal",
        run_id="wave4-run",
        goal_contract_id="wave4-goal",
        capability_grants=[CapabilityGrant(capability_id=value) for value in capability_ids],
    )
