from __future__ import annotations

import json
from dataclasses import asdict

import typer

from zeus_agent.connector_runtime import (
    ConnectorDeclaration,
    ConnectorKind,
    ConnectorLifecycleRegistry,
    ConnectorLifecycleState,
)
from zeus_agent.eval.wave4 import run_wave4_eval
from zeus_agent.gateway_runtime.drafts import draft_cron_command, draft_gateway_command
from zeus_agent.kernel.authority import AuthorityContext, CapabilityGrant
from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.kernel.capabilities import CapabilityDescriptor, CapabilityRisk
from zeus_agent.security.credentials import (
    CredentialScope,
    credential_report,
    redact_secret_like,
)
from zeus_agent.workflow_runtime.jobs import CompensationMetadata, RetryPolicy, WorkflowPlanner


def register_wave4_commands(app: typer.Typer) -> None:
    @app.command("wave4-connectors")
    def wave4_connectors(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(_wave4_connector_payload(), as_json=as_json)

    @app.command("wave4-workflow")
    def wave4_workflow(
        secret_like: str = typer.Option(
            "sk-wave4-secret",
            "--secret-like",
            help="Secret-like sample value used to prove redaction behavior.",
        ),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(_wave4_workflow_payload(secret_like=secret_like), as_json=as_json)

    @app.command("wave4-eval")
    def wave4_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave4_eval(), as_json=as_json)


def _wave4_connector_payload() -> dict[str, object]:
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
    handlers = registry.build_stub_handlers()
    unhealthy_handler_calls = {"count": 0}
    source_unhealthy_handler = handlers["api.fetch"]

    def tracked_unhealthy_handler(payload: dict[str, object]) -> dict[str, object]:
        unhealthy_handler_calls["count"] += 1
        return source_unhealthy_handler(payload)

    handlers["api.fetch"] = tracked_unhealthy_handler
    broker = CapabilityBroker(graph=graph, handlers=handlers)
    authority = _authority(["mcp.echo", "api.fetch"])
    model_visible_tools = [
        entry["function"]["name"]
        for entry in graph.compile_model_schema(profile="coding-agent", authority=authority)
    ]
    healthy_dispatch = broker.dispatch(capability_id="mcp.echo", payload={}, context=authority)
    unhealthy_dispatch = broker.dispatch(capability_id="api.fetch", payload={}, context=authority)
    return {
        "fake_local_only": True,
        "no_external_side_effects": True,
        "lifecycle_report": registry.lifecycle_report(),
        "discovered_tool_names": registry.discovered_tool_names(),
        "model_visible_tools": model_visible_tools,
        "healthy_dispatch": healthy_dispatch,
        "unhealthy_dispatch": unhealthy_dispatch,
        "unhealthy_handler_executed": unhealthy_handler_calls["count"] > 0,
    }


def _wave4_workflow_payload(*, secret_like: str) -> dict[str, object]:
    scopes = [CredentialScope.parse("external.openai.readonly")]
    credential = credential_report(scopes)
    planner = WorkflowPlanner()
    job = planner.plan(
        principal_id="principal-wave4",
        session_id="session-wave4",
        job_id="job-wave4-001",
        idempotency_key="idem-wave4-001",
        retry_policy=RetryPolicy(max_attempts=3, backoff_seconds=5),
        compensation=CompensationMetadata(command="revert-cache", target="orders-cache"),
    )
    retry_job = planner.next_retry(job)
    gateway = draft_gateway_command(
        command="send --api-key {0} --to queue://dispatch".format(secret_like),
        target="gateway.dispatch",
    )
    cron = draft_cron_command(
        command="install --token=secret --schedule */5 * * * *",
        target="cron.scheduler",
    )
    secret_redaction_payload = {"input": redact_secret_like(secret_like)}
    no_secret_echo = secret_like not in json.dumps(
        {
            "credential": credential,
            "workflow_job": asdict(job),
            "retry_job": asdict(retry_job),
            "gateway_draft": asdict(gateway),
            "cron_draft": asdict(cron),
            "secret_redaction": secret_redaction_payload,
        },
        sort_keys=True,
    )
    return {
        "fake_local_only": True,
        "no_external_side_effects": True,
        "no_secret_echo": no_secret_echo,
        "credential": credential,
        "workflow_job": asdict(job),
        "retry_job": asdict(retry_job),
        "gateway_draft": asdict(gateway),
        "cron_draft": asdict(cron),
        "secret_redaction": secret_redaction_payload,
    }


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


def _print_payload(payload: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
