import json

from typer.testing import CliRunner

from zeus_agent.cli import app


def test_cli_blueprint_approve_status_loop(tmp_path):
    runner = CliRunner()
    home = tmp_path / "zeus-home"

    init_result = runner.invoke(app, ["init", "--home", str(home), "--json"])
    assert init_result.exit_code == 0

    blueprint_result = runner.invoke(
        app,
        [
            "blueprint",
            "Create a local analysis report",
            "--home",
            str(home),
            "--workspace",
            str(tmp_path),
            "--json",
        ],
    )
    assert blueprint_result.exit_code == 0
    blueprint = json.loads(blueprint_result.stdout)
    run_id = blueprint["run_id"]
    assert blueprint["approval_state"] == "pending_approval"

    approve_result = runner.invoke(app, ["approve", run_id, "--home", str(home), "--json"])
    assert approve_result.exit_code == 0
    approved = json.loads(approve_result.stdout)
    assert approved["status"]["approval_state"] == "approved"

    status_result = runner.invoke(app, ["status", run_id, "--home", str(home), "--json"])
    assert status_result.exit_code == 0
    status = json.loads(status_result.stdout)
    assert status["execution_mode"] == "sandbox_after_approval"


def test_cli_registry_and_github_prep(tmp_path):
    runner = CliRunner()
    home = tmp_path / "zeus-home"

    provider_result = runner.invoke(
        app,
        ["provider-add", "openai", "OPENAI_API_KEY", "--home", str(home), "--json"],
    )
    assert provider_result.exit_code == 0

    route_result = runner.invoke(
        app,
        [
            "model-route-add",
            "planning",
            "openai",
            "gpt-example",
            "--home",
            str(home),
            "--json",
        ],
    )
    assert route_result.exit_code == 0

    plan_result = runner.invoke(
        app,
        ["github-prep", "Orvek-dev/Zeus", "--home", str(home), "--json"],
    )
    assert plan_result.exit_code == 0
    plan = json.loads(plan_result.stdout)
    assert plan["repo"] == "Orvek-dev/Zeus"
    assert plan["ready"] is False
