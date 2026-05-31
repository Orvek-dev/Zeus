"""Zeus command line interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import typer

from zeus_agent.agent.session import ZeusAgentSession
from zeus_agent.core.approvals import approve_run, reject_run, run_status
from zeus_agent.core.blueprint import build_blueprint
from zeus_agent.core.mneme import diff_gate, list_evidence, record_command_evidence
from zeus_agent.core.plugins import list_plugins, register_plugin
from zeus_agent.core.registry import (
    add_model_route,
    add_provider,
    create_github_publish_plan,
    list_github_publish_plans,
    list_model_routes,
    list_tools,
    provider_status,
    register_tool,
)
from zeus_agent.core.scheduler import add_cron_job, list_cron_jobs
from zeus_agent.eval.trajectory import export_run_trajectory
from zeus_agent.gateway.adapters import list_gateway_adapters, register_gateway_adapter
from zeus_agent.observability.reports import build_system_report
from zeus_agent.core.sisyphus import pursue_run
from zeus_agent.core.skills import (
    draft_skill,
    list_skills,
    promote_skill,
    retire_skill,
    test_skill,
)
from zeus_agent.paths import init_home
from zeus_agent.runtime.backends import DEFAULT_RUNTIME_BACKENDS
from zeus_agent.runtime.sandbox import SandboxRuntime
from zeus_agent.schemas.trace_event import new_trace_event
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.run_store import RunStore
from zeus_agent.storage.state import StateStore

app = typer.Typer(
    name="zeus",
    help="Local-first goal-to-agent control plane.",
    no_args_is_help=True,
)
console = Console()


def _print_json(value: object) -> None:
    console.print_json(json.dumps(value, ensure_ascii=False))


@app.command("init")
def init_cmd(
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Create local Zeus state directories."""

    paths = init_home(home)
    payload = {name: str(path) for name, path in paths.items()}
    if json_output:
        _print_json(payload)
        return
    table = Table(title="Zeus local state")
    table.add_column("Name")
    table.add_column("Path")
    for name, path in payload.items():
        table.add_row(name, path)
    console.print(table)


@app.command("blueprint")
def blueprint_cmd(
    request: Annotated[str, typer.Argument(help="User goal to turn into a Zeus blueprint.")],
    workspace: Annotated[
        Path | None,
        typer.Option("--workspace", "-w", help="Workspace boundary for the planned run."),
    ] = None,
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Create a plan-only GoalContract and ExecutionSpec."""

    bundle = build_blueprint(request, workspace=workspace)
    store = RunStore(home)
    artifacts = store.save_blueprint(bundle.goal_contract, bundle.execution_spec)
    EventLog(home).append(
        new_trace_event(
            "blueprint.created",
            run_id=bundle.execution_spec.run_id,
            actor="zeus",
            payload={
                "goal_id": bundle.goal_contract.goal_id,
                "risk_level": bundle.goal_contract.risk_level,
                "artifacts": artifacts.as_dict(),
            },
        )
    )
    payload = {
        "run_id": bundle.execution_spec.run_id,
        "goal_id": bundle.goal_contract.goal_id,
        "approval_state": bundle.goal_contract.approval_state,
        "execution_status": bundle.execution_spec.status,
        "risk_level": bundle.goal_contract.risk_level,
        "normalized_goal": bundle.goal_contract.normalized_goal,
        "artifacts": artifacts.as_dict(),
        "redaction_summary": bundle.redaction_summary,
    }
    if json_output:
        _print_json(payload)
        return
    console.print(
        Panel.fit(
            "\n".join(
                [
                    "[bold]Blueprint created[/bold]",
                    f"Run: {bundle.execution_spec.run_id}",
                    f"Goal: {bundle.goal_contract.normalized_goal}",
                    f"Risk: {bundle.goal_contract.risk_level}",
                    f"State: {bundle.goal_contract.approval_state}",
                    f"GoalContract: {artifacts.goal_contract_path}",
                    f"ExecutionSpec: {artifacts.execution_spec_path}",
                ]
            ),
            title="Zeus",
        )
    )
    console.print("Approve with: [bold]zeus approve " + bundle.execution_spec.run_id + "[/bold]")


@app.command("approve")
def approve_cmd(
    run_id: Annotated[str, typer.Argument(help="Run id created by zeus blueprint.")],
    text: Annotated[
        str,
        typer.Option("--text", help="Optional approval note."),
    ] = "",
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Approve a blueprint so later execution stages may start."""

    record, status = approve_run(run_id, approval_text=text, home=home)
    payload = {"approval": record.model_dump(mode="json"), "status": status}
    if json_output:
        _print_json(payload)
        return
    console.print(f"[green]Approved[/green] {run_id}")
    console.print(f"Approval: {record.approval_id}")
    console.print(f"Execution mode: {status['execution_mode']}")


@app.command("reject")
def reject_cmd(
    run_id: Annotated[str, typer.Argument(help="Run id created by zeus blueprint.")],
    reason: Annotated[
        str,
        typer.Option("--reason", help="Optional rejection reason."),
    ] = "",
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Reject a blueprint and prevent execution from starting."""

    record, status = reject_run(run_id, reason=reason, home=home)
    payload = {"approval": record.model_dump(mode="json"), "status": status}
    if json_output:
        _print_json(payload)
        return
    console.print(f"[red]Rejected[/red] {run_id}")
    console.print(f"Approval: {record.approval_id}")
    console.print(f"State: {status['approval_state']}")


@app.command("status")
def status_cmd(
    run_id: Annotated[str, typer.Argument(help="Run id created by zeus blueprint.")],
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Show the state of a Zeus run."""

    status = run_status(run_id, home=home)
    if json_output:
        _print_json(status)
        return
    table = Table(title=f"Zeus run {run_id}")
    table.add_column("Field")
    table.add_column("Value")
    for key in (
        "approval_state",
        "execution_status",
        "execution_mode",
        "risk_level",
        "normalized_goal",
        "approval_count",
    ):
        table.add_row(key, str(status[key]))
    console.print(table)
    console.print(f"Run directory: {status['artifacts']['run_dir']}")


@app.command("runs")
def runs_cmd(
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of runs to list."),
    ] = 20,
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """List recent Zeus runs."""

    runs = RunStore(home).list_runs(limit=limit)
    if json_output:
        _print_json(runs)
        return
    table = Table(title="Recent Zeus runs")
    table.add_column("Run")
    table.add_column("State")
    table.add_column("Risk")
    table.add_column("Goal")
    for item in runs:
        risk = ""
        try:
            risk = RunStore(home).load_goal_contract(item["run_id"]).risk_level
        except FileNotFoundError:
            risk = "unknown"
        table.add_row(item["run_id"], item["status"], risk, item["goal"])
    console.print(table)


@app.command("execute")
def execute_cmd(
    run_id: Annotated[str, typer.Argument(help="Run id created by zeus blueprint.")],
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Advance an approved run through the Sisyphus control loop."""

    report = pursue_run(run_id, home=home)
    if json_output:
        _print_json(report.model_dump(mode="json"))
        return
    console.print(f"Sisyphus status: [bold]{report.status}[/bold]")
    console.print(f"Progress: {report.progress_score:.2f}")
    for reason in report.escalation_reasons:
        console.print(f"[yellow]Escalation:[/yellow] {reason}")


@app.command("pursue")
def pursue_cmd(
    run_id: Annotated[str, typer.Argument(help="Run id created by zeus blueprint.")],
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Alias for execute."""

    execute_cmd(run_id, home=home, json_output=json_output)


@app.command("sandbox-snapshot")
def sandbox_snapshot_cmd(
    run_id: Annotated[str, typer.Argument(help="Approved run id.")],
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Capture a workspace checkpoint for an approved run."""

    checkpoint = SandboxRuntime(home).create_checkpoint(run_id)
    if json_output:
        _print_json(checkpoint.model_dump(mode="json"))
        return
    console.print(f"Checkpoint: {checkpoint.checkpoint_id}")
    console.print(f"Files: {checkpoint.file_count}")


@app.command("sandbox-run", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def sandbox_run_cmd(
    ctx: typer.Context,
    run_id: Annotated[str, typer.Argument(help="Approved run id.")],
    timeout: Annotated[
        int | None,
        typer.Option("--timeout", help="Command timeout in seconds, capped by run budget."),
    ] = None,
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Run a command in the approved local process sandbox."""

    argv = list(ctx.args)
    if argv and argv[0] == "--":
        argv = argv[1:]
    result = SandboxRuntime(home).run_command(run_id, argv, timeout_seconds=timeout)
    record_command_evidence(run_id, result, home=home)
    if json_output:
        _print_json(result.model_dump(mode="json"))
        return
    console.print(f"Exit: {result.exit_code}")
    if result.stdout:
        console.print(result.stdout)
    if result.stderr:
        console.print(result.stderr)


@app.command("mneme-diff")
def mneme_diff_cmd(
    run_id: Annotated[str, typer.Argument(help="Run id to inspect.")],
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Run the Mneme diff gate for a run."""

    report = diff_gate(run_id, home=home)
    if json_output:
        _print_json(report.model_dump(mode="json"))
        return
    console.print(f"Diff gate allowed: {report.allowed}")
    console.print(report.summary)
    for path in report.changed_files:
        console.print(f"- {path}")


@app.command("evidence")
def evidence_cmd(
    run_id: Annotated[str, typer.Argument(help="Run id to inspect.")],
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """List Mneme evidence for a run."""

    records = list_evidence(run_id, home=home)
    if json_output:
        _print_json(records)
        return
    table = Table(title="Mneme evidence")
    table.add_column("Evidence")
    table.add_column("Type")
    table.add_column("Passed")
    table.add_column("Summary")
    for record in records:
        table.add_row(record["evidence_id"], record["evidence_type"], str(record["passed"]), record["summary"])
    console.print(table)


@app.command("skill-draft")
def skill_draft_cmd(
    name: Annotated[str, typer.Argument(help="Skill name.")],
    description: Annotated[str, typer.Argument(help="Skill purpose.")],
    trigger: list[str] = typer.Option([], "--trigger", help="Trigger phrase. Repeatable."),
    procedure: Annotated[
        str,
        typer.Option("--procedure", help="Reusable skill procedure."),
    ] = "",
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Draft a local reusable Zeus skill."""

    manifest = draft_skill(name, description, triggers=trigger, procedure=procedure, home=home)
    if json_output:
        _print_json(manifest.model_dump(mode="json"))
        return
    console.print(f"Drafted skill: {manifest.skill_id}")


@app.command("skill-test")
def skill_test_cmd(
    skill_id: Annotated[str, typer.Argument(help="Skill id.")],
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Evaluate a skill before promotion."""

    manifest = test_skill(skill_id, home=home)
    if json_output:
        _print_json(manifest.model_dump(mode="json"))
        return
    console.print(f"Skill state: {manifest.state}")
    if manifest.evaluation:
        console.print(f"Passed: {manifest.evaluation.passed} score={manifest.evaluation.score:.2f}")


@app.command("skill-promote")
def skill_promote_cmd(
    skill_id: Annotated[str, typer.Argument(help="Skill id.")],
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Promote a tested skill."""

    manifest = promote_skill(skill_id, home=home)
    if json_output:
        _print_json(manifest.model_dump(mode="json"))
        return
    console.print(f"Promoted skill: {skill_id}")


@app.command("skill-retire")
def skill_retire_cmd(
    skill_id: Annotated[str, typer.Argument(help="Skill id.")],
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Retire a skill."""

    manifest = retire_skill(skill_id, home=home)
    if json_output:
        _print_json(manifest.model_dump(mode="json"))
        return
    console.print(f"Retired skill: {skill_id}")


@app.command("skills")
def skills_cmd(
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """List local Zeus skills."""

    skills = list_skills(home=home)
    if json_output:
        _print_json(skills)
        return
    table = Table(title="Zeus skills")
    table.add_column("Skill")
    table.add_column("State")
    table.add_column("Score")
    table.add_column("Name")
    for skill in skills:
        table.add_row(skill["skill_id"], skill["state"], skill["score"], skill["name"])
    console.print(table)


@app.command("provider-add")
def provider_add_cmd(
    provider: Annotated[str, typer.Argument(help="Provider name.")],
    env_var: Annotated[str, typer.Argument(help="Environment variable holding the API key.")],
    base_url: Annotated[
        str | None,
        typer.Option("--base-url", help="Optional provider base URL."),
    ] = None,
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Register provider auth without storing secrets."""

    provider_config = add_provider(provider, env_var, base_url=base_url, home=home)
    if json_output:
        _print_json(provider_config.model_dump(mode="json"))
        return
    console.print(f"Provider registered: {provider}")


@app.command("providers")
def providers_cmd(
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """List provider auth configs and env-var status."""

    providers = provider_status(home=home)
    if json_output:
        _print_json(providers)
        return
    table = Table(title="Zeus providers")
    table.add_column("Provider")
    table.add_column("Env Var")
    table.add_column("Configured")
    for provider in providers:
        table.add_row(str(provider["provider"]), str(provider["env_var"]), str(provider["configured"]))
    console.print(table)


@app.command("model-route-add")
def model_route_add_cmd(
    purpose: Annotated[str, typer.Argument(help="Route purpose, e.g. planning or coding.")],
    provider: Annotated[str, typer.Argument(help="Provider name.")],
    model: Annotated[str, typer.Argument(help="Model id.")],
    priority: Annotated[int, typer.Option("--priority", help="Lower priority wins.")] = 100,
    max_cost_usd: Annotated[float, typer.Option("--max-cost-usd", help="Per-run cost ceiling.")] = 0.0,
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Add a model route."""

    route = add_model_route(purpose, provider, model, priority=priority, max_cost_usd=max_cost_usd, home=home)
    if json_output:
        _print_json(route.model_dump(mode="json"))
        return
    console.print(f"Route registered: {route.route_id}")


@app.command("model-routes")
def model_routes_cmd(
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """List model routes."""

    routes = [route.model_dump(mode="json") for route in list_model_routes(home=home)]
    if json_output:
        _print_json(routes)
        return
    table = Table(title="Zeus model routes")
    table.add_column("Purpose")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Priority")
    for route in routes:
        table.add_row(str(route["purpose"]), str(route["provider"]), str(route["model"]), str(route["priority"]))
    console.print(table)


@app.command("tool-register")
def tool_register_cmd(
    name: Annotated[str, typer.Argument(help="Tool name.")],
    description: Annotated[str, typer.Argument(help="Tool description.")],
    risk_level: Annotated[str, typer.Option("--risk", help="low, medium, or high.")] = "medium",
    network_access: Annotated[str, typer.Option("--network", help="none, allowlist, or open.")] = "none",
    command: list[str] = typer.Option([], "--command", help="Command element. Repeatable."),
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Register a tool definition for future orchestration."""

    tool = register_tool(name, description, risk_level=risk_level, network_access=network_access, command=command, home=home)
    if json_output:
        _print_json(tool.model_dump(mode="json"))
        return
    console.print(f"Tool registered: {tool.tool_id}")


@app.command("tools")
def tools_cmd(
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """List registered tools."""

    tools = [tool.model_dump(mode="json") for tool in list_tools(home=home)]
    if json_output:
        _print_json(tools)
        return
    table = Table(title="Zeus tools")
    table.add_column("Name")
    table.add_column("Risk")
    table.add_column("Approval")
    for tool in tools:
        table.add_row(str(tool["name"]), str(tool["risk_level"]), str(tool["requires_approval"]))
    console.print(table)


@app.command("github-prep")
def github_prep_cmd(
    repo: Annotated[str, typer.Argument(help="Target GitHub repository, e.g. Orvek-dev/Zeus.")],
    remote: Annotated[str, typer.Option("--remote", help="Git remote name.")] = "origin",
    branch: Annotated[str, typer.Option("--branch", help="Publish branch.")] = "main",
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Create a GitHub publishing preparation plan without pushing."""

    plan = create_github_publish_plan(repo, remote=remote, branch=branch, home=home)
    if json_output:
        _print_json(plan.model_dump(mode="json"))
        return
    console.print(f"GitHub publish plan: {plan.plan_id}")


@app.command("github-plans")
def github_plans_cmd(
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """List GitHub publishing preparation plans."""

    plans = [plan.model_dump(mode="json") for plan in list_github_publish_plans(home=home)]
    if json_output:
        _print_json(plans)
        return
    table = Table(title="GitHub publish plans")
    table.add_column("Plan")
    table.add_column("Repo")
    table.add_column("Ready")
    for plan in plans:
        table.add_row(str(plan["plan_id"]), str(plan["repo"]), str(plan["ready"]))
    console.print(table)


@app.command("agent-run")
def agent_run_cmd(
    run_id: Annotated[str, typer.Argument(help="Approved run id.")],
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Run one Zeus agent control cycle through the guarded tool broker."""

    report = ZeusAgentSession(run_id, home=home).run_control_cycle()
    if json_output:
        _print_json(report.model_dump(mode="json"))
        return
    console.print(f"Agent session: {report.session_id}")
    console.print(f"Status: {report.status}")
    for result in report.tool_results:
        console.print(f"- {result.name}: {result.status} - {result.summary}")


@app.command("memory-search")
def memory_search_cmd(
    query: Annotated[str, typer.Argument(help="Search query for local Zeus session memory.")],
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Search the local SQLite state store."""

    rows = StateStore(home).search_messages(query)
    if json_output:
        _print_json(rows)
        return
    table = Table(title="Zeus memory search")
    table.add_column("Session")
    table.add_column("Role")
    table.add_column("Content")
    for row in rows:
        table.add_row(str(row["session_id"]), str(row["role"]), str(row["content"])[:120])
    console.print(table)


@app.command("sandbox-restore")
def sandbox_restore_cmd(
    run_id: Annotated[str, typer.Argument(help="Approved run id.")],
    snapshot_id: Annotated[str, typer.Argument(help="Snapshot id from a checkpoint manifest.")],
    prune_untracked: Annotated[
        bool,
        typer.Option("--prune-untracked", help="Remove untracked files not present in the snapshot."),
    ] = False,
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Restore files from a content-addressed checkpoint snapshot."""

    report = SandboxRuntime(home).restore_checkpoint(run_id, snapshot_id, prune_untracked=prune_untracked)
    if json_output:
        _print_json(report.model_dump(mode="json"))
        return
    console.print(f"Restore: {report.restore_id}")
    console.print(f"Restored files: {len(report.restored_files)}")
    if report.skipped_files:
        console.print(f"[yellow]Skipped:[/yellow] {len(report.skipped_files)}")


@app.command("runtime-backends")
def runtime_backends_cmd(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """List configured runtime backend slots."""

    backends = [backend.__dict__ for backend in DEFAULT_RUNTIME_BACKENDS.list()]
    if json_output:
        _print_json(backends)
        return
    table = Table(title="Zeus runtime backends")
    table.add_column("Name")
    table.add_column("Isolation")
    table.add_column("Available")
    table.add_column("Notes")
    for backend in backends:
        table.add_row(str(backend["name"]), str(backend["isolation"]), str(backend["available"]), str(backend["notes"]))
    console.print(table)


@app.command("plugin-register")
def plugin_register_cmd(
    name: Annotated[str, typer.Argument(help="Plugin or MCP server name.")],
    kind: Annotated[str, typer.Option("--kind", help="local_plugin, mcp_server, or tool_pack.")] = "local_plugin",
    description: Annotated[str, typer.Option("--description", help="Plugin description.")] = "",
    entrypoint: Annotated[str, typer.Option("--entrypoint", help="Command, URL, or module reference.")] = "",
    risk_level: Annotated[str, typer.Option("--risk", help="low, medium, or high.")] = "medium",
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Register a local plugin, MCP server, or tool pack."""

    plugin = register_plugin(
        name,
        kind=kind,  # type: ignore[arg-type]
        description=description,
        entrypoint=entrypoint,
        risk_level=risk_level,  # type: ignore[arg-type]
        home=home,
    )
    if json_output:
        _print_json(plugin.model_dump(mode="json"))
        return
    console.print(f"Plugin registered: {plugin.plugin_id}")


@app.command("plugins")
def plugins_cmd(
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """List plugin and MCP registrations."""

    plugins = [plugin.model_dump(mode="json") for plugin in list_plugins(home=home)]
    if json_output:
        _print_json(plugins)
        return
    table = Table(title="Zeus plugins")
    table.add_column("Name")
    table.add_column("Kind")
    table.add_column("Risk")
    table.add_column("Enabled")
    for plugin in plugins:
        table.add_row(str(plugin["name"]), str(plugin["kind"]), str(plugin["risk_level"]), str(plugin["enabled"]))
    console.print(table)


@app.command("cron-add")
def cron_add_cmd(
    name: Annotated[str, typer.Argument(help="Job name.")],
    schedule: Annotated[str, typer.Argument(help="Cron expression or schedule label.")],
    command: list[str] = typer.Option([], "--command", help="Command element. Repeatable."),
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Record a cron-style job plan without installing a daemon."""

    job = add_cron_job(name, schedule, command, home=home)
    if json_output:
        _print_json(job.model_dump(mode="json"))
        return
    console.print(f"Cron job registered: {job.job_id}")


@app.command("cron-jobs")
def cron_jobs_cmd(
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """List cron-style job plans."""

    jobs = [job.model_dump(mode="json") for job in list_cron_jobs(home=home)]
    if json_output:
        _print_json(jobs)
        return
    table = Table(title="Zeus cron jobs")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Enabled")
    for job in jobs:
        table.add_row(str(job["name"]), str(job["schedule"]), str(job["enabled"]))
    console.print(table)


@app.command("gateway-register")
def gateway_register_cmd(
    platform: Annotated[str, typer.Argument(help="Platform name, e.g. slack, discord, api.")],
    mode: Annotated[str, typer.Option("--mode", help="read_only, draft_only, or approved_send.")] = "draft_only",
    secret_env: list[str] = typer.Option([], "--secret-env", help="Secret env var reference. Repeatable."),
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Register a gateway adapter in disabled/draft-first mode."""

    adapter = register_gateway_adapter(
        platform,
        mode=mode,  # type: ignore[arg-type]
        secret_env_vars=secret_env,
        home=home,
    )
    if json_output:
        _print_json(adapter.model_dump(mode="json"))
        return
    console.print(f"Gateway adapter registered: {adapter.adapter_id}")


@app.command("gateways")
def gateways_cmd(
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """List gateway adapters."""

    adapters = [adapter.model_dump(mode="json") for adapter in list_gateway_adapters(home=home)]
    if json_output:
        _print_json(adapters)
        return
    table = Table(title="Zeus gateways")
    table.add_column("Platform")
    table.add_column("Mode")
    table.add_column("Enabled")
    for adapter in adapters:
        table.add_row(str(adapter["platform"]), str(adapter["mode"]), str(adapter["enabled"]))
    console.print(table)


@app.command("trajectory-export")
def trajectory_export_cmd(
    run_id: Annotated[str, typer.Argument(help="Run id to export.")],
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Export a run trajectory for evaluation and replay."""

    path = export_run_trajectory(run_id, home=home)
    payload = {"run_id": run_id, "trajectory_path": str(path)}
    if json_output:
        _print_json(payload)
        return
    console.print(f"Trajectory: {path}")


@app.command("doctor")
def doctor_cmd(
    home: Annotated[
        Path | None,
        typer.Option("--home", help="Override ZEUS_HOME for this command."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Show a local Zeus system report."""

    report = build_system_report(home=home)
    if json_output:
        _print_json(report)
        return
    console.print(Panel.fit(f"Home: {report['home']}\nState DB: {report['state_db']}", title="Zeus doctor"))
    console.print(f"Runs: {len(report['runs'])}")
    console.print(f"Runtime backends: {len(report['runtime_backends'])}")
    console.print(f"Plugins: {len(report['plugins'])}")
