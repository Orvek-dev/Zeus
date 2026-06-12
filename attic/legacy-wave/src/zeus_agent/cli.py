from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict, Optional

import typer
from pydantic import ValidationError

from zeus_agent.agent_runtime import run_wave2_loop
from zeus_agent.acp_runtime import handle_acp_message
from zeus_agent.adaptive_zeus_runtime import build_adaptive_zeus_contract
from zeus_agent.api_runtime import run_api_server
from zeus_agent.batch_runtime import run_objective_batch
from zeus_agent.cli_objective import register_objective_commands
from zeus_agent.cli_objective_card import register_objective_card_commands
from zeus_agent.cli_objective_run import register_objective_run_commands
from zeus_agent.cli_welcome import register_welcome_commands
from zeus_agent.cli_wave3 import register_wave3_commands
from zeus_agent.cli_wave4 import register_wave4_commands
from zeus_agent.cli_wave5 import register_wave5_commands
from zeus_agent.cli_wave6 import register_wave6_commands
from zeus_agent.cli_wave7 import register_wave7_commands
from zeus_agent.cli_wave8 import register_wave8_commands
from zeus_agent.cli_wave9 import register_wave9_commands
from zeus_agent.cli_wave10 import register_wave10_commands
from zeus_agent.cli_wave11 import register_wave11_commands
from zeus_agent.cli_wave12 import register_wave12_commands
from zeus_agent.cli_wave13 import register_wave13_commands
from zeus_agent.cli_wave14 import register_wave14_commands
from zeus_agent.cli_wave15 import register_wave15_commands
from zeus_agent.cli_wave16 import register_wave16_commands
from zeus_agent.cli_wave17 import register_wave17_commands
from zeus_agent.cli_wave18 import register_wave18_commands
from zeus_agent.cli_wave19 import register_wave19_commands
from zeus_agent.cli_wave20 import register_wave20_commands
from zeus_agent.cli_wave37 import register_wave37_commands
from zeus_agent.cli_wave38 import register_wave38_commands
from zeus_agent.cli_wave39 import register_wave39_commands
from zeus_agent.cli_wave40 import register_wave40_commands
from zeus_agent.cli_wave41 import register_wave41_commands
from zeus_agent.cli_wave42 import register_wave42_commands
from zeus_agent.cli_wave43 import register_wave43_commands
from zeus_agent.cli_wave44 import register_wave44_commands
from zeus_agent.cli_wave45 import register_wave45_commands
from zeus_agent.cli_wave46 import register_wave46_commands
from zeus_agent.cli_wave47 import register_wave47_commands
from zeus_agent.cli_wave48 import register_wave48_commands
from zeus_agent.cli_wave49 import register_wave49_commands
from zeus_agent.cli_wave51 import register_wave51_commands
from zeus_agent.cli_wave52 import register_wave52_commands
from zeus_agent.cli_wave53 import register_wave53_commands
from zeus_agent.cli_wave54 import register_wave54_commands
from zeus_agent.cli_wave55 import register_wave55_commands
from zeus_agent.cli_wave56 import register_wave56_commands
from zeus_agent.cli_wave57 import register_wave57_commands
from zeus_agent.cli_wave58 import register_wave58_commands
from zeus_agent.cli_wave59 import register_wave59_commands
from zeus_agent.cli_wave60 import register_wave60_commands
from zeus_agent.cli_wave61 import register_wave61_commands
from zeus_agent.cli_wave63 import register_wave63_commands
from zeus_agent.cli_wave65 import register_wave65_commands
from zeus_agent.cli_wave67 import register_wave67_commands
from zeus_agent.cli_wave76 import register_wave76_commands
from zeus_agent.cli_wave84 import register_wave84_commands
from zeus_agent.cli_wave85 import register_wave85_commands
from zeus_agent.cli_wave86 import register_wave86_commands
from zeus_agent.cli_wave87 import register_wave87_commands
from zeus_agent.cli_wave88 import register_wave88_commands
from zeus_agent.cli_wave89 import register_wave89_commands
from zeus_agent.cli_wave90 import register_wave90_commands
from zeus_agent.cli_wave91 import register_wave91_commands
from zeus_agent.cli_wave92 import register_wave92_commands
from zeus_agent.cli_wave93 import register_wave93_commands
from zeus_agent.cli_wave94 import register_wave94_commands
from zeus_agent.cli_wave95 import register_wave95_commands
from zeus_agent.cli_wave96 import register_wave96_commands
from zeus_agent.cli_wave97 import register_wave97_commands
from zeus_agent.cli_wave98 import register_wave98_commands
from zeus_agent.cli_wave99 import register_wave99_commands
from zeus_agent.cli_wave100 import register_wave100_commands
from zeus_agent.cli_wave101 import register_wave101_commands
from zeus_agent.cli_wave102 import register_wave102_commands
from zeus_agent.cli_wave103 import register_wave103_commands
from zeus_agent.cli_wave104 import register_wave104_commands
from zeus_agent.cli_wave105 import register_wave105_commands
from zeus_agent.cli_wave106 import register_wave106_commands
from zeus_agent.cli_wave107 import register_wave107_commands
from zeus_agent.cli_wave108 import register_wave108_commands
from zeus_agent.cli_wave109 import register_wave109_commands
from zeus_agent.cli_wave110 import register_wave110_commands
from zeus_agent.cli_wave111 import register_wave111_commands
from zeus_agent.cli_wave112 import register_wave112_commands
from zeus_agent.cli_wave113 import register_wave113_commands
from zeus_agent.cli_wave114 import register_wave114_commands
from zeus_agent.cli_wave115 import register_wave115_commands
from zeus_agent.cli_wave116 import register_wave116_commands
from zeus_agent.cli_wave117 import register_wave117_commands
from zeus_agent.cli_wave118 import register_wave118_commands
from zeus_agent.cli_wave119 import register_wave119_commands
from zeus_agent.cli_wave120 import register_wave120_commands
from zeus_agent.cli_wave121 import register_wave121_commands
from zeus_agent.cli_wave122 import register_wave122_commands
from zeus_agent.cli_wave123 import register_wave123_commands
from zeus_agent.cli_wave124 import register_wave124_commands
from zeus_agent.cli_wave125 import register_wave125_commands
from zeus_agent.cli_wave127 import register_wave127_commands
from zeus_agent.cli_wave128 import register_wave128_commands
from zeus_agent.cli_wave129 import register_wave129_commands
from zeus_agent.cli_wave130 import register_wave130_commands
from zeus_agent.cli_wave131 import register_wave131_commands
from zeus_agent.cli_wave132 import register_wave132_commands
from zeus_agent.cli_wave133 import register_wave133_commands
from zeus_agent.cli_wave134 import register_wave134_commands
from zeus_agent.cli_wave135 import register_wave135_commands
from zeus_agent.cli_wave136 import register_wave136_commands
from zeus_agent.cli_wave137 import register_wave137_commands
from zeus_agent.cli_wave138 import register_wave138_commands
from zeus_agent.cli_wave139 import register_wave139_commands
from zeus_agent.cli_wave140 import register_wave140_commands
from zeus_agent.cli_wave141 import register_wave141_commands
from zeus_agent.cli_wave142 import register_wave142_commands
from zeus_agent.cli_wave143 import register_wave143_commands
from zeus_agent.cli_wave144 import register_wave144_commands
from zeus_agent.cli_wave145 import register_wave145_commands
from zeus_agent.cli_wave146 import register_wave146_commands
from zeus_agent.cli_wave148 import register_wave148_commands
from zeus_agent.cli_wave154 import register_wave154_commands
from zeus_agent.cli_wave156 import register_wave156_commands
from zeus_agent.cli_wave157 import register_wave157_commands
from zeus_agent.cli_wave158 import register_wave158_commands
from zeus_agent.cli_wave160 import register_wave160_commands
from zeus_agent.cli_wave300 import register_wave300_commands
from zeus_agent.cli_wave301 import register_wave301_commands
from zeus_agent.cli_wave302 import register_wave302_commands
from zeus_agent.cli_wave303 import register_wave303_commands
from zeus_agent.cli_wave304 import register_wave304_commands
from zeus_agent.cli_wave305 import register_wave305_commands
from zeus_agent.cli_wave306 import register_wave306_commands
from zeus_agent.cli_wave307 import register_wave307_commands
from zeus_agent.cli_wave308 import register_wave308_commands
from zeus_agent.cli_wave309 import register_wave309_commands
from zeus_agent.cli_wave310 import register_wave310_commands
from zeus_agent.cli_wave311 import register_wave311_commands
from zeus_agent.cli_wave312 import register_wave312_commands
from zeus_agent.cli_wave313 import register_wave313_commands
from zeus_agent.cli_wave314 import register_wave314_commands
from zeus_agent.cli_wave315 import register_wave315_commands
from zeus_agent.cli_wave316 import register_wave316_commands
from zeus_agent.cli_wave317 import register_wave317_commands
from zeus_agent.cli_wave318 import register_wave318_commands
from zeus_agent.cli_wave319 import register_wave319_commands
from zeus_agent.cli_wave320 import register_wave320_commands
from zeus_agent.cli_wave321 import register_wave321_commands
from zeus_agent.cli_wave322 import register_wave322_commands
from zeus_agent.cli_wave323 import register_wave323_commands
from zeus_agent.cli_live_research_workflow import register_live_research_workflow_commands
from zeus_agent.cli_g006 import register_g006_commands
from zeus_agent.cli_total import register_total_commands
from zeus_agent.cli_final import register_final_commands
from zeus_agent.kernel.authority import AuthorityContext, CapabilityGrant, PathGrant
from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.kernel.capabilities import (
    CapabilityDescriptor,
    CapabilityGraph,
    CapabilityRisk,
    SideEffect,
)
from zeus_agent.doctor_runtime import doctor_report
from zeus_agent.entry_runtime import ZeusChatRuntime, default_zeus_home, entry_status_payload
from zeus_agent.eval import run_golden_journeys
from zeus_agent.gateway_runtime import gateway_adapter_catalog_payload
from zeus_agent.governed_live_connector_platform_runtime import build_governed_live_connector_platform
from zeus_agent.governed_live_slice_runtime import build_governed_live_slice
from zeus_agent.higher_order_agent_os_runtime import build_higher_order_agent_os
from zeus_agent.live_beta_candidate_runtime import build_live_beta_candidate_contract
from zeus_agent.live_beta_candidate_runtime import parse_live_beta_candidate_scenario
from zeus_agent.live_platform_beta_runtime import build_live_platform_beta
from zeus_agent.memory_graph_runtime import MemoryGraphStore
from zeus_agent.memory_ontology_surface_runtime import build_memory_ontology_surface_contract
from zeus_agent.mcp_runtime import curated_mcp_catalog_payload
from zeus_agent.model_runtime import (
    evaluate_provider_fallback,
    provider_budget_payload,
    provider_catalog_payload,
)
from zeus_agent.objective_compiler_ux_runtime import build_objective_compiler_workflow
from zeus_agent.objective_run_runtime import ObjectiveRunRuntime, ObjectiveRunStore
from zeus_agent.orchestration_runtime import DynamicWorkflowCompiler, WorkflowCompileRequest
from zeus_agent.plugin_runtime import validate_plugin_manifest
from zeus_agent.platform_surface_runtime import build_platform_surface_contract
from zeus_agent.research_runtime import build_research_brief
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.session_runtime import SessionStore
from zeus_agent.setup_runtime import setup_apply, setup_plan
from zeus_agent.tool_runtime import native_tool_catalog_payload
from zeus_agent.tool_limbs_runtime import build_tool_limbs_contract
from zeus_agent.trajectory_runtime import export_trajectory
from zeus_agent.verification_runtime import ReviewBindingRequest, bind_review
from zeus_agent.wiki_runtime import render_wiki_page
from zeus_agent.workflow_runtime import StandingOrderRequest, StandingOrderRuntime

app = typer.Typer(
    no_args_is_help=True,
    help=(
        "Zeus Agent CLI. "
        "This surface exposes governed local runtime, provider, tool, transport, "
        "conversation, production scaffold, and final architecture checks."
    ),
)


def _version_callback(value: bool) -> None:
    if value:
        from zeus_agent import __version__

        typer.echo("zeus-agent {0}".format(__version__))
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed zeus-agent version and exit.",
    ),
) -> None:
    return None


@app.command("kernel-status")
def kernel_status() -> None:
    typer.echo(
        "Zeus governed kernel is active. "
        "Use --help to inspect local runtime, provider, tool, transport, and eval commands."
    )


@app.command("zeus-chat")
def zeus_chat(
    message: str = typer.Option(..., "--message", "-m", help="Message to send to Zeus chat mode."),
    session_id: str = typer.Option("default", "--session-id"),
    provider_id: Optional[str] = typer.Option(None, "--provider-id"),
    profile: str = typer.Option("chat", "--profile"),
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    runtime = ZeusChatRuntime(home or default_zeus_home())
    payload = runtime.run_turn(
        message=message,
        session_id=session_id,
        provider_id=provider_id,
        profile=profile,
    ).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("status")
def status(
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    _print_payload(entry_status_payload(home or default_zeus_home()), as_json=as_json)


@app.command("objective-start")
def objective_start(
    objective: str = typer.Option(..., "--objective"),
    session_id: str = typer.Option("default", "--session-id"),
    principal_id: str = typer.Option("operator.local", "--principal-id"),
    acceptance_criterion: list[str] = typer.Option([], "--acceptance-criterion"),
    constraint: list[str] = typer.Option([], "--constraint"),
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    runtime = ObjectiveRunRuntime(ObjectiveRunStore(home or default_zeus_home()))
    payload = runtime.start(
        objective=objective,
        session_id=session_id,
        principal_id=principal_id,
        acceptance_criteria=tuple(acceptance_criterion),
        constraints=tuple(constraint),
    ).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("objective-status")
def objective_status(
    run_id: str = typer.Option(..., "--run-id"),
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    runtime = ObjectiveRunRuntime(ObjectiveRunStore(home or default_zeus_home()))
    _print_payload(runtime.status(run_id).to_payload(), as_json=as_json)


@app.command("objective-export")
def objective_export(
    run_id: str = typer.Option(..., "--run-id"),
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    runtime = ObjectiveRunRuntime(ObjectiveRunStore(home or default_zeus_home()))
    _print_payload(runtime.export(run_id).to_payload(), as_json=as_json)


@app.command("objective-compile-workflow")
def objective_compile_workflow(
    objective: str = typer.Option(..., "--objective"),
    session_id: str = typer.Option("default", "--session-id"),
    principal_id: str = typer.Option("operator.local", "--principal-id"),
    task_count: int = typer.Option(1, "--task-count"),
    requires_code: bool = typer.Option(False, "--requires-code"),
    requires_research: bool = typer.Option(False, "--requires-research"),
    risk_level: str = typer.Option("normal", "--risk-level"),
    interview_answer: list[str] = typer.Option([], "--interview-answer"),
    cognitive_provider_output: Optional[str] = typer.Option(None, "--cognitive-provider-output"),
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    payload = build_objective_compiler_workflow(
        home=home or default_zeus_home(),
        objective=objective,
        session_id=session_id,
        principal_id=principal_id,
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
        interview_answers=tuple(interview_answer),
        cognitive_provider_output=cognitive_provider_output,
    ).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("governed-live-slice")
def governed_live_slice(
    surface: str = typer.Option("provider", "--surface"),
    capability_id: str = typer.Option("provider.local-smoke", "--capability-id"),
    scenario: str = typer.Option("local-smoke", "--scenario"),
    objective_run_id: Optional[str] = typer.Option(None, "--objective-run-id"),
    lease_ref: Optional[str] = typer.Option(None, "--lease-ref"),
    approval_ref: Optional[str] = typer.Option(None, "--approval-ref"),
    promotion_guard_ref: Optional[str] = typer.Option(None, "--promotion-guard-ref"),
    broker_evidence_ref: Optional[str] = typer.Option(None, "--broker-evidence-ref"),
    credential_scope: Optional[str] = typer.Option(None, "--credential-scope"),
    sandbox_policy_ref: Optional[str] = typer.Option(None, "--sandbox-policy-ref"),
    audit_receipt_ref: Optional[str] = typer.Option(None, "--audit-receipt-ref"),
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    _ = home or default_zeus_home()
    payload = build_governed_live_slice(
        surface=surface,
        capability_id=capability_id,
        scenario=scenario,
        objective_run_id=objective_run_id,
        lease_ref=lease_ref,
        approval_ref=approval_ref,
        promotion_guard_ref=promotion_guard_ref,
        broker_evidence_ref=broker_evidence_ref,
        credential_scope=credential_scope,
        sandbox_policy_ref=sandbox_policy_ref,
        audit_receipt_ref=audit_receipt_ref,
    ).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("governed-live-connectors")
def governed_live_connectors(
    scenario: str = typer.Option("status", "--scenario"),
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    payload = build_governed_live_connector_platform(
        home=home or default_zeus_home(),
        scenario=scenario,
    ).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("higher-order-agent-os")
def higher_order_agent_os(
    scenario: str = typer.Option("status", "--scenario"),
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    payload = build_higher_order_agent_os(
        home=home or default_zeus_home(),
        scenario=scenario,
    ).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("live-platform-beta")
def live_platform_beta(
    scenario: str = typer.Option("status", "--scenario"),
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    payload = build_live_platform_beta(
        home=home or default_zeus_home(),
        scenario=scenario,
    ).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("release-gated-ulw")
def release_gated_ulw(
    target_version: str = typer.Option(..., "--target-version"),
    raw_secret_marker_detected: bool = typer.Option(False, "--raw-secret-marker-detected"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    payload = build_release_gated_ulw_status(
        target_version=target_version,
        raw_secret_marker_detected=raw_secret_marker_detected,
    ).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("tool-limbs")
def tool_limbs(
    tool_id: Optional[str] = typer.Option(None, "--tool-id"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    payload = build_tool_limbs_contract(tool_id=tool_id).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("platform-surface")
def platform_surface(
    surface_id: Optional[str] = typer.Option(None, "--surface"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    payload = build_platform_surface_contract(surface_id=surface_id).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("memory-ontology")
def memory_ontology(
    home: Optional[Path] = typer.Option(None, "--home"),
    subject: Optional[str] = typer.Option(None, "--subject"),
    candidate_id: Optional[str] = typer.Option(None, "--candidate-id"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    payload = build_memory_ontology_surface_contract(
        home=home or default_zeus_home(),
        subject=subject,
        candidate_id=candidate_id,
    ).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("adaptive-zeus")
def adaptive_zeus(
    objective: str = typer.Option(..., "--objective"),
    task_count: int = typer.Option(1, "--task-count"),
    requires_code: bool = typer.Option(False, "--requires-code"),
    requires_research: bool = typer.Option(False, "--requires-research"),
    risk_level: str = typer.Option("normal", "--risk-level"),
    evidence_target: str = typer.Option("v010.adaptive_zeus", "--evidence-target"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    payload = build_adaptive_zeus_contract(
        objective=objective,
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        risk_level=risk_level,
        evidence_target=evidence_target,
    ).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("live-beta-candidate")
def live_beta_candidate(
    include_smoke: bool = typer.Option(False, "--include-smoke"),
    scenario: str = typer.Option("happy", "--scenario"),
    operator_note: Optional[str] = typer.Option(None, "--operator-note"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        parsed_scenario = parse_live_beta_candidate_scenario(scenario)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    payload = build_live_beta_candidate_contract(
        include_smoke=include_smoke,
        scenario=parsed_scenario,
        operator_note=operator_note,
    ).to_payload()
    _print_payload(payload, as_json=as_json)


@app.command("setup")
def setup(
    provider_id: str = typer.Option("fake", "--provider-id"),
    home: Optional[Path] = typer.Option(None, "--home"),
    mcp: bool = typer.Option(False, "--mcp"),
    mcp_server: list[str] = typer.Option([], "--mcp-server", help="Catalog MCP server alias to configure when --write is used. Repeatable."),
    gateway: bool = typer.Option(False, "--gateway", help="Configure a local quarantined gateway target when --write is used."),
    gateway_adapter: Optional[str] = typer.Option(None, "--gateway-adapter", help="Gateway adapter alias, e.g. slack."),
    gateway_target: Optional[str] = typer.Option(None, "--gateway-target", help="Gateway target to allowlist locally, e.g. slack://ops."),
    local: bool = typer.Option(False, "--local"),
    write: bool = typer.Option(False, "--write", help="Write local first-run model/MCP/gateway config."),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    if write:
        payload = setup_apply(
            home=home or default_zeus_home(),
            provider_id=provider_id,
            mcp=mcp,
            mcp_servers=tuple(mcp_server),
            gateway=gateway,
            gateway_adapter=gateway_adapter,
            gateway_target=gateway_target,
            local=local,
        )
        _print_payload(payload, as_json=as_json)
        return
    payload = setup_plan(
        home=home or default_zeus_home(),
        provider_id=provider_id,
        mcp=mcp,
        gateway=gateway,
        gateway_adapter=gateway_adapter,
        gateway_target=gateway_target,
        local=local,
    )
    _print_payload(payload, as_json=as_json)


@app.command("doctor")
def doctor(
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    _print_payload(doctor_report(home or default_zeus_home()), as_json=as_json)


@app.command("providers")
def providers(
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    _print_payload(provider_catalog_payload(), as_json=as_json)


@app.command("tool-catalog")
def tool_catalog(
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    _print_payload(native_tool_catalog_payload(), as_json=as_json)


@app.command("mcp-catalog")
def mcp_catalog(
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    _print_payload(curated_mcp_catalog_payload(), as_json=as_json)


@app.command("provider-fallback-check")
def provider_fallback_check(
    primary_provider_id: str = typer.Option("local-llm", "--primary-provider-id"),
    fallback_provider_id: str = typer.Option("openai", "--fallback-provider-id"),
    budget_required: int = typer.Option(1, "--budget-required"),
    live_transport: bool = typer.Option(False, "--live-transport"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    lease = RuntimeLease(
        lease_id="wave21.lease.provider",
        objective_id="wave21.objective.provider",
        principal_id="wave21.principal.local",
        run_id="wave21.run.provider",
        allowed_capabilities=("provider.external.generate", "provider.local.generate"),
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.com",),
        budget_limit=10,
        evidence_target="mneme.wave21.provider",
        live_transport_allowed=live_transport,
    )
    payload = evaluate_provider_fallback(
        primary_provider_id=primary_provider_id,
        fallback_provider_id=fallback_provider_id,
        lease=lease,
        budget_required=budget_required,
    ).to_payload()
    payload["budget"] = provider_budget_payload(
        provider_id=fallback_provider_id,
        lease=lease,
        budget_required=budget_required,
    )
    _print_payload(payload, as_json=as_json)


@app.command("session-list")
def session_list(
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    store = SessionStore(home or default_zeus_home())
    payload = {
        "sessions": [session.to_payload() for session in store.list_sessions()],
        "live_production_claimed": False,
    }
    _print_payload(payload, as_json=as_json)


@app.command("session-export")
def session_export(
    session_id: str = typer.Option("default", "--session-id"),
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    store = SessionStore(home or default_zeus_home())
    _print_payload(store.export_session(session_id), as_json=as_json)


@app.command("memory-fact-add")
def memory_fact_add(
    subject: str = typer.Option(..., "--subject"),
    predicate: str = typer.Option(..., "--predicate"),
    object_text: str = typer.Option(..., "--object-text"),
    provenance_id: str = typer.Option(..., "--provenance-id"),
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    store = MemoryGraphStore(home or default_zeus_home())
    fact = store.propose_fact(
        subject=subject,
        predicate=predicate,
        object_text=object_text,
        provenance_id=provenance_id,
    )
    _print_payload(fact.to_payload(), as_json=as_json)


@app.command("wiki-page")
def wiki_page(
    subject: str = typer.Option(..., "--subject"),
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    store = MemoryGraphStore(home or default_zeus_home())
    _print_payload(render_wiki_page(store, subject).to_payload(), as_json=as_json)


@app.command("plugin-validate")
def plugin_validate(
    manifest_json: str = typer.Option(..., "--manifest-json"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        raw = json.loads(manifest_json)
    except JSONDecodeError:
        raw = manifest_json
    _print_payload(validate_plugin_manifest(raw).model_dump(mode="json"), as_json=as_json)


@app.command("trajectory-export")
def trajectory_export(
    run_id: str = typer.Option(..., "--run-id"),
    events_json: str = typer.Option(..., "--events-json"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        raw = json.loads(events_json)
    except JSONDecodeError:
        raw = []
    events = tuple(item for item in raw if isinstance(item, dict)) if isinstance(raw, list) else ()
    _print_payload(export_trajectory(run_id=run_id, events=events).model_dump(mode="json"), as_json=as_json)


@app.command("batch-run")
def batch_run(
    batch_id: str = typer.Option(..., "--batch-id"),
    items_json: str = typer.Option(..., "--items-json"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        raw = json.loads(items_json)
    except JSONDecodeError:
        raw = []
    objectives = tuple(item for item in raw if isinstance(item, str)) if isinstance(raw, list) else ()
    _print_payload(run_objective_batch(batch_id=batch_id, objectives=objectives), as_json=as_json)


@app.command("acp-handle")
def acp_handle(
    message_json: str = typer.Option(..., "--message-json"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        raw = json.loads(message_json)
    except JSONDecodeError:
        raw = {}
    message = raw if isinstance(raw, dict) else {}
    _print_payload(handle_acp_message(message), as_json=as_json)


@app.command("standing-order-plan")
def standing_order_plan(
    request_json: str = typer.Option(..., "--request-json"),
    live_transport: bool = typer.Option(False, "--live-transport"),
    no_lease: bool = typer.Option(False, "--no-lease"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        raw = json.loads(request_json)
        request = StandingOrderRequest.model_validate(raw if isinstance(raw, dict) else {})
    except (JSONDecodeError, ValidationError, TypeError) as exc:
        _print_payload({"decision": "blocked", "reason": "malformed_standing_order", "error": str(exc)}, as_json=as_json)
        raise typer.Exit(code=1)
    now = datetime.now(timezone.utc)
    lease = None if no_lease else RuntimeLease(
        lease_id="wave29.lease.cron",
        objective_id="wave29.objective.cron",
        principal_id="wave29.principal.operator",
        run_id="wave29.run.cron",
        allowed_capabilities=("cron.schedule.tick",),
        credential_scopes=("external.gateway.readonly",),
        network_hosts=("gateway.local",),
        budget_limit=100,
        evidence_target=request.evidence_target,
        live_transport_allowed=live_transport,
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    payload = StandingOrderRuntime().plan(
        request=request,
        lease=lease,
        now=now,
    ).model_dump(mode="json")
    _print_payload(payload, as_json=as_json)


@app.command("review-bind")
def review_bind(
    review_json: str = typer.Option(..., "--review-json"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        raw = json.loads(review_json)
        request = ReviewBindingRequest.model_validate(raw if isinstance(raw, dict) else {})
    except (JSONDecodeError, ValidationError, TypeError) as exc:
        _print_payload({"decision": "blocked", "reason": "malformed_review", "error": str(exc)}, as_json=as_json)
        raise typer.Exit(code=1)
    _print_payload(bind_review(request).model_dump(mode="json"), as_json=as_json)


@app.command("workflow-compile")
def workflow_compile(
    objective: str = typer.Option(..., "--objective"),
    task_count: int = typer.Option(1, "--task-count"),
    requires_code: bool = typer.Option(False, "--requires-code"),
    requires_research: bool = typer.Option(False, "--requires-research"),
    risk_level: str = typer.Option("normal", "--risk-level"),
    evidence_target: str = typer.Option("mneme.wave31.workflow", "--evidence-target"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    try:
        request = WorkflowCompileRequest(
            objective=objective,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
            evidence_target=evidence_target,
        )
    except ValidationError as exc:
        _print_payload({"decision": "blocked", "reason": "malformed_workflow_request", "error": str(exc)}, as_json=as_json)
        raise typer.Exit(code=1)
    _print_payload(DynamicWorkflowCompiler().compile(request).model_dump(mode="json"), as_json=as_json)


@app.command("research-brief")
def research_brief(
    query: str = typer.Option(..., "--query"),
    objective_id: str = typer.Option("wave32.research", "--objective-id"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    _print_payload(
        build_research_brief(objective_id=objective_id, query=query),
        as_json=as_json,
    )


@app.command("golden-journeys")
def golden_journeys(
    home: Optional[Path] = typer.Option(None, "--home"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    _print_payload(run_golden_journeys(home=home or default_zeus_home()), as_json=as_json)


@app.command("gateway-adapters")
def gateway_adapters(
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    _print_payload(gateway_adapter_catalog_payload(), as_json=as_json)


@app.command("browser-plan")
def browser_plan(
    target_url: str = typer.Option(..., "--target-url"),
    evidence_target: str = typer.Option("mneme.wave36.browser", "--evidence-target"),
    live: bool = typer.Option(False, "--live"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    from zeus_agent.browser_runtime import BrowserDispatchFacade, BrowserDispatchRequest

    result = BrowserDispatchFacade().plan(
        BrowserDispatchRequest(
            target_url=target_url,
            dry_run=not live,
            evidence_target=evidence_target,
        )
    )
    _print_payload(result.model_dump(mode="json"), as_json=as_json)


@app.command("terminal-plan")
def terminal_plan(
    command: str = typer.Option(..., "--command"),
    root: Optional[Path] = typer.Option(None, "--root"),
    evidence_target: str = typer.Option("mneme.wave36.terminal", "--evidence-target"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    from zeus_agent.terminal_runtime import TerminalDispatchFacade, TerminalDispatchRequest

    result = TerminalDispatchFacade().plan(
        TerminalDispatchRequest(
            command=command,
            root=root,
            evidence_target=evidence_target,
        )
    )
    _print_payload(result.model_dump(mode="json"), as_json=as_json)


@app.command("sandbox-plan")
def sandbox_plan(
    command: str = typer.Option(..., "--command"),
    root: Optional[Path] = typer.Option(None, "--root"),
    mount: Optional[str] = typer.Option(None, "--mount"),
    evidence_target: str = typer.Option("mneme.wave36.sandbox", "--evidence-target"),
    cleanup_plan: str = typer.Option("remove temporary workspace after evidence capture", "--cleanup-plan"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    from zeus_agent.sandbox_runtime import SandboxDispatchFacade, SandboxDispatchRequest

    result = SandboxDispatchFacade().plan(
        SandboxDispatchRequest(
            root=root,
            mounts=(mount,) if mount is not None else (),
            commands=(command,),
            cleanup_required=True,
            cleanup_plan=cleanup_plan,
            evidence_target=evidence_target,
        )
    )
    _print_payload(result.model_dump(mode="json"), as_json=as_json)


@app.command("api-serve")
def api_serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
    home: Optional[Path] = typer.Option(None, "--home"),
) -> None:
    typer.echo(
        "Zeus API server listening on {0}:{1}; live production claimed=false".format(
            host,
            port,
        ),
    )
    run_api_server(host, port, home or default_zeus_home())


def _wave1_kernel_graph() -> CapabilityGraph:
    return CapabilityGraph(
        [
            CapabilityDescriptor(
                capability_id="file.read",
                name="file.read",
                risk=CapabilityRisk.low,
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                output_schema={"type": "object"},
                description="Read-only in-memory stub operation for Wave 1 kernel dump.",
            ),
            CapabilityDescriptor(
                capability_id="terminal.run",
                name="terminal.run",
                risk=CapabilityRisk.high,
                input_schema={"type": "object", "properties": {"cmd": {"type": "string"}}},
                output_schema={"type": "object"},
                side_effects=[SideEffect.local_process],
                description="Mutating local-process capability descriptor for Wave 1 checks.",
            ),
        ]
    )


def _default_authority_context(granted_capabilities: list[str]) -> AuthorityContext:
    path_grants = []
    if "file.read" in set(granted_capabilities):
        path_grants.append(PathGrant(capability_id="file.read", path_prefix="/virtual/"))
    return AuthorityContext(
        principal_id="wave1-principal",
        run_id="wave1-run",
        goal_contract_id="wave1-goal",
        capability_grants=[CapabilityGrant(capability_id=value) for value in granted_capabilities],
        path_grants=path_grants,
    )


def _load_authority_context(authority_json: Optional[str]) -> AuthorityContext:
    if authority_json is None:
        return _default_authority_context(["file.read"])
    parsed = json.loads(authority_json)
    return AuthorityContext.model_validate(parsed)


def _print_payload(payload: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))


@app.command("kernel-dump")
def kernel_dump(
    scenario: str = typer.Option(
        "approved-read",
        "--scenario",
        help=(
            "Wave 1 kernel dump scenario. "
            "Use approved-read or unapproved-terminal to inspect broker decisions."
        ),
    ),
    authority_json: Optional[str] = typer.Option(
        None,
        "--authority-json",
        help=(
            "Optional authority JSON override for Wave 1 kernel dump. "
            "Malformed or invalid authority input fails closed."
        ),
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON output for Wave 1 kernel dump.",
    ),
) -> None:
    if scenario not in {"approved-read", "unapproved-terminal"}:
        raise typer.BadParameter("scenario must be one of: approved-read, unapproved-terminal")

    try:
        authority = _load_authority_context(authority_json)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        error_payload = {
            "error": "invalid_authority_json: {0}".format(str(exc)),
            "principal_id": "invalid",
            "model_visible_capabilities": [],
            "allowed_capabilities": [],
        }
        _print_payload(error_payload, as_json=as_json)
        raise typer.Exit(code=1)

    graph = _wave1_kernel_graph()
    handler_marker = {"terminal_run_called": False}

    def read_handler(payload: dict[str, object]) -> dict[str, object]:
        return {"path": payload.get("path"), "content": "wave1_stub"}

    def terminal_handler(payload: dict[str, object]) -> dict[str, object]:
        handler_marker["terminal_run_called"] = True
        return {"accepted": bool(payload)}

    broker = CapabilityBroker(
        graph=graph,
        handlers={"file.read": read_handler, "terminal.run": terminal_handler},
    )
    capability_id = "file.read" if scenario == "approved-read" else "terminal.run"
    payload = {"path": "/virtual/wave1.txt"} if capability_id == "file.read" else {"cmd": "echo noop"}
    response = broker.dispatch(capability_id=capability_id, payload=payload, context=authority)

    visible = graph.compile_model_schema(
        profile="coding-agent",
        authority=authority,
        approval_receipts=None,
    )
    visible_names = [entry["function"]["name"] for entry in visible]
    blocked_capabilities = [
        value for value in ["file.read", "terminal.run"] if value not in set(visible_names)
    ]
    output = {
        "scenario": scenario,
        "model_visible_capabilities": visible_names,
        "blocked_capabilities": blocked_capabilities,
        "allowed_capabilities": [value for value in ["file.read", "terminal.run"] if value not in blocked_capabilities],
        "decision": response["decision"],
        "capability_id": response["capability_id"],
        "result": response.get("result"),
        "reason": response.get("reason"),
        "evidence": response["evidence"],
        "handler_executed": handler_marker["terminal_run_called"],
    }
    _print_payload(output, as_json=as_json)


@app.command("wave2-loop")
def wave2_loop(
    scenario: str = typer.Option(
        "happy",
        "--scenario",
        help="Wave 2 fake local loop scenario. Use happy or blocked.",
    ),
    home: Optional[Path] = typer.Option(
        None,
        "--home",
        help="Optional local state home for the SQLite fake loop database.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Print structured JSON output for the Wave 2 fake loop.",
    ),
) -> None:
    if scenario not in {"happy", "blocked"}:
        raise typer.BadParameter("scenario must be one of: happy, blocked")
    state_home = home if home is not None else Path(tempfile.mkdtemp(prefix="zeus-wave2-"))
    payload = run_wave2_loop(scenario=scenario, home=state_home)
    _print_payload(payload, as_json=as_json)

register_wave3_commands(app)
register_wave4_commands(app)
register_wave5_commands(app)
register_wave6_commands(app)
register_wave7_commands(app)
register_wave8_commands(app)
register_wave9_commands(app)
register_wave10_commands(app)
register_wave11_commands(app)
register_wave12_commands(app)
register_wave13_commands(app)
register_wave14_commands(app)
register_wave15_commands(app)
register_wave16_commands(app)
register_wave17_commands(app)
register_wave18_commands(app)
register_wave19_commands(app)
register_wave20_commands(app)
register_wave37_commands(app)
register_wave38_commands(app)
register_wave39_commands(app)
register_wave40_commands(app)
register_wave41_commands(app)
register_wave42_commands(app)
register_wave43_commands(app)
register_wave44_commands(app)
register_wave45_commands(app)
register_wave46_commands(app)
register_wave47_commands(app)
register_wave48_commands(app)
register_wave49_commands(app)
register_wave51_commands(app)
register_wave52_commands(app)
register_wave53_commands(app)
register_wave54_commands(app)
register_wave55_commands(app)
register_wave56_commands(app)
register_wave57_commands(app)
register_wave58_commands(app)
register_wave59_commands(app)
register_wave60_commands(app)
register_wave61_commands(app)
register_wave63_commands(app)
register_wave65_commands(app)
register_wave67_commands(app)
register_wave76_commands(app)
register_wave84_commands(app)
register_wave85_commands(app)
register_wave86_commands(app)
register_wave87_commands(app)
register_wave88_commands(app)
register_wave89_commands(app)
register_wave90_commands(app)
register_wave91_commands(app)
register_wave92_commands(app)
register_wave93_commands(app)
register_wave94_commands(app)
register_wave95_commands(app)
register_wave96_commands(app)
register_wave97_commands(app)
register_wave98_commands(app)
register_wave99_commands(app)
register_wave100_commands(app)
register_wave101_commands(app)
register_wave102_commands(app)
register_wave103_commands(app)
register_wave104_commands(app)
register_wave105_commands(app)
register_wave106_commands(app)
register_wave107_commands(app)
register_wave108_commands(app)
register_wave109_commands(app)
register_wave110_commands(app)
register_wave111_commands(app)
register_wave112_commands(app)
register_wave113_commands(app)
register_wave114_commands(app)
register_wave115_commands(app)
register_wave116_commands(app)
register_wave117_commands(app)
register_wave118_commands(app)
register_wave119_commands(app)
register_wave120_commands(app)
register_wave121_commands(app)
register_wave122_commands(app)
register_wave123_commands(app)
register_wave124_commands(app)
register_wave125_commands(app)
register_wave127_commands(app)
register_wave128_commands(app)
register_wave129_commands(app)
register_wave130_commands(app)
register_wave131_commands(app)
register_wave132_commands(app)
register_wave133_commands(app)
register_wave134_commands(app)
register_wave135_commands(app)
register_wave136_commands(app)
register_wave137_commands(app)
register_wave138_commands(app)
register_wave139_commands(app)
register_wave140_commands(app)
register_wave141_commands(app)
register_wave142_commands(app)
register_wave143_commands(app)
register_wave144_commands(app)
register_wave145_commands(app)
register_wave146_commands(app)
register_wave148_commands(app)
register_wave154_commands(app)
register_wave156_commands(app)
register_wave157_commands(app)
register_wave158_commands(app)
register_wave160_commands(app)
register_wave300_commands(app)
register_wave301_commands(app)
register_wave302_commands(app)
register_wave303_commands(app)
register_wave304_commands(app)
register_wave305_commands(app)
register_wave306_commands(app)
register_wave307_commands(app)
register_wave308_commands(app)
register_wave309_commands(app)
register_wave310_commands(app)
register_wave311_commands(app)
register_wave312_commands(app)
register_wave313_commands(app)
register_wave314_commands(app)
register_wave315_commands(app)
register_wave316_commands(app)
register_wave317_commands(app)
register_wave318_commands(app)
register_wave319_commands(app)
register_wave320_commands(app)
register_wave321_commands(app)
register_wave322_commands(app)
register_wave323_commands(app)
register_live_research_workflow_commands(app)
register_g006_commands(app)
register_total_commands(app)
register_final_commands(app)
register_objective_card_commands(app)
register_objective_commands(app)
register_objective_run_commands(app)
register_welcome_commands(app)
