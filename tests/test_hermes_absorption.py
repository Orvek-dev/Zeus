import json
import sys

from typer.testing import CliRunner

from zeus_agent.agent.session import ZeusAgentSession
from zeus_agent.cli import app
from zeus_agent.core.approvals import approve_run
from zeus_agent.core.blueprint import build_blueprint
from zeus_agent.core.plugins import list_plugins, register_plugin
from zeus_agent.core.scheduler import add_cron_job, list_cron_jobs
from zeus_agent.eval.trajectory import export_run_trajectory
from zeus_agent.gateway.adapters import list_gateway_adapters, register_gateway_adapter
from zeus_agent.observability.reports import build_system_report
from zeus_agent.runtime.backends import DEFAULT_RUNTIME_BACKENDS
from zeus_agent.runtime.sandbox import SandboxRuntime
from zeus_agent.schemas.agent import ToolCallRequest
from zeus_agent.storage.run_store import RunStore
from zeus_agent.storage.state import StateStore


def _approved_run(tmp_path):
    home = tmp_path / "zeus-home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# demo\n", encoding="utf-8")
    bundle = build_blueprint("Build a small local artifact", workspace=workspace)
    store = RunStore(home)
    store.save_blueprint(bundle.goal_contract, bundle.execution_spec)
    approve_run(bundle.execution_spec.run_id, home=home)
    return home, workspace, bundle.execution_spec.run_id


def test_agent_session_routes_tools_and_indexes_memory(tmp_path):
    home, _, run_id = _approved_run(tmp_path)
    session = ZeusAgentSession(run_id, home=home)

    report = session.run_tool_calls(
        [
            ToolCallRequest(
                name="zeus.record_note",
                arguments={"summary": "agent memory marker", "note": "searchable zeus memory"},
                requires_approval=False,
            ),
            ToolCallRequest(
                name="zeus.sandbox_command",
                arguments={"argv": [sys.executable, "-c", "print('agent-ok')"]},
            ),
        ]
    )

    assert report.status == "completed"
    assert StateStore(home).search_messages("agent-ok") or StateStore(home).search_messages("memory")


def test_checkpoint_restore_uses_content_addressed_store(tmp_path):
    home, workspace, run_id = _approved_run(tmp_path)
    runtime = SandboxRuntime(home)

    checkpoint = runtime.create_checkpoint(run_id)
    assert checkpoint.restorable is True
    assert checkpoint.content_snapshot_path
    snapshot_id = checkpoint.content_snapshot_path.rsplit("/", 1)[-1].removesuffix(".json")

    (workspace / "README.md").write_text("# changed\n", encoding="utf-8")
    report = runtime.restore_checkpoint(run_id, snapshot_id)

    assert "README.md" in report.restored_files
    assert (workspace / "README.md").read_text(encoding="utf-8") == "# demo\n"


def test_p1_p2_registries_reports_and_trajectory(tmp_path):
    home, _, run_id = _approved_run(tmp_path)

    plugin = register_plugin("local mcp", kind="mcp_server", home=home)
    job = add_cron_job("daily review", "0 9 * * *", ["zeus", "doctor"], home=home)
    adapter = register_gateway_adapter("slack", mode="draft_only", secret_env_vars=["SLACK_BOT_TOKEN"], home=home)
    trajectory = export_run_trajectory(run_id, home=home)
    report = build_system_report(home=home)

    assert list_plugins(home=home)[0].plugin_id == plugin.plugin_id
    assert list_cron_jobs(home=home)[0].job_id == job.job_id
    assert list_gateway_adapters(home=home)[0].adapter_id == adapter.adapter_id
    assert trajectory.exists()
    assert report["runtime_backends"]
    assert any(item.name == "local-process" for item in DEFAULT_RUNTIME_BACKENDS.list())


def test_new_cli_surface_smoke(tmp_path):
    home, _, run_id = _approved_run(tmp_path)
    runner = CliRunner()

    for args in (
        ["agent-run", run_id, "--home", str(home), "--json"],
        ["runtime-backends", "--json"],
        ["plugin-register", "demo", "--home", str(home), "--json"],
        ["cron-add", "demo", "daily", "--command", "zeus", "--command", "doctor", "--home", str(home), "--json"],
        ["gateway-register", "api", "--home", str(home), "--json"],
        ["trajectory-export", run_id, "--home", str(home), "--json"],
        ["doctor", "--home", str(home), "--json"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.stdout
        json.loads(result.stdout)

