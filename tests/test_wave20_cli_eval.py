from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import typer
from typer.testing import CliRunner

from zeus_agent.cli_wave20 import register_wave20_commands

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = PROJECT_ROOT / "src"
LOCAL_TESTS = PROJECT_ROOT / "tests"


def local_src_tests_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(LOCAL_SRC), str(LOCAL_TESTS)))
    return env


def test_wave20_cli_registration_outputs_gate_json_without_secret_echo() -> None:
    # Given: an isolated Typer app exposes only the Wave20 observability commands.
    app = typer.Typer()
    register_wave20_commands(app)
    runner = CliRunner()
    raw_secret = "sk-wave20-cli-secret"

    # When: happy and blocked gate commands run through the local CLI surface.
    happy = runner.invoke(app, ["wave20-observability-gates", "--json"])
    blocked = runner.invoke(
        app,
        ["wave20-observability-gates-blocks", "--secret-like", raw_secret, "--json"],
    )

    # Then: both commands emit the requested JSON contracts without secret echo.
    assert happy.exit_code == 0, happy.stdout
    assert blocked.exit_code == 0, blocked.stdout
    happy_payload = json.loads(happy.stdout)
    blocked_payload = json.loads(blocked.stdout)
    assert happy_payload["observability_gate_created"] is True
    assert happy_payload["release_no_claim_gate"] == "pass"
    assert happy_payload["production_release_blocked"] is True
    assert happy_payload["release_approval_evidence_id"] is None
    assert blocked_payload["secret_echo"] == "blocked"
    assert blocked_payload["raw_secret_present"] is False
    assert raw_secret not in blocked.stdout


def test_wave20_cli_rejects_empty_secret_fixture() -> None:
    # Given: an isolated Typer app exposes the blocked-path redaction scenario.
    app = typer.Typer()
    register_wave20_commands(app)
    runner = CliRunner()

    # When: the caller passes an empty secret fixture.
    result = runner.invoke(app, ["wave20-observability-gates-blocks", "--secret-like", "", "--json"])

    # Then: the CLI rejects the malformed security fixture instead of producing false evidence.
    assert result.exit_code == 2
    assert "raw_secret_present" not in result.stdout


def test_wave20_cli_default_block_fixture_exercises_secret_echo_gate() -> None:
    # Given: an isolated Typer app exposes the blocked-path redaction scenario.
    app = typer.Typer()
    register_wave20_commands(app)
    runner = CliRunner()

    # When: the caller uses the default blocked-path fixture.
    result = runner.invoke(app, ["wave20-observability-gates-blocks", "--json"])

    # Then: the default command still exercises the secret-echo block.
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["secret_echo"] == "blocked"
    assert payload["raw_secret_present"] is False


def test_wave20_package_cli_outputs_eval_json() -> None:
    # Given: the package CLI is the user-visible Wave20 eval surface.
    env = local_src_tests_env()

    # When: Wave20 eval runs through python -m zeus_agent against local src/tests.
    payload = json.loads(
        subprocess.check_output(
            [sys.executable, "-m", "zeus_agent", "wave20-eval", "--json"],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
        ),
    )

    # Then: the registered package CLI emits the G007 regression fields.
    assert payload["suite"] == "wave20"
    assert payload["failed"] == 0
    assert payload["observability_gates_ok"] is True
    assert payload["production_release_blocked"] is True
    assert payload["release_approval_evidence_id"] is None
    assert payload["live_production_claimed"] is False
