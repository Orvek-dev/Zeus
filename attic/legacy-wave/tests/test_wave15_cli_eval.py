from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import typer
from typer.testing import CliRunner

from zeus_agent.cli_wave15 import register_wave15_commands

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = PROJECT_ROOT / "src"
LOCAL_TESTS = PROJECT_ROOT / "tests"


def local_src_tests_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(LOCAL_SRC), str(LOCAL_TESTS)))
    return env


def test_wave15_cli_registration_outputs_live_agent_json(tmp_path: Path) -> None:
    # Given: an isolated Typer app with only Wave15 commands registered.
    app = typer.Typer()
    register_wave15_commands(app)
    runner = CliRunner()
    home = tmp_path / "wave15-state"

    # When: happy and blocked commands run through the CLI surface.
    happy = runner.invoke(
        app,
        ["wave15-live-agent", "--scenario", "tool-loop", "--home", str(home), "--json"],
    )
    blocks = runner.invoke(
        app,
        [
            "wave15-live-agent-blocks",
            "--secret-like",
            "sk-live-agent-fixture",
            "--home",
            str(home),
            "--json",
        ],
    )

    # Then: both commands emit the requested JSON contracts without secret echo.
    assert happy.exit_code == 0, happy.stdout
    assert blocks.exit_code == 0, blocks.stdout
    happy_payload = json.loads(happy.stdout)
    blocks_payload = json.loads(blocks.stdout)
    assert happy_payload["live_agent_loop_created"] is True
    assert happy_payload["provider_decision"] == "selected"
    assert happy_payload["tool_calls_processed"] >= 1
    assert happy_payload["audit_events"] >= 1
    assert happy_payload["audit_record_created"] is True
    assert happy_payload["network_opened"] is False
    assert blocks_payload["missing_provider_lease"] == "blocked"
    assert blocks_payload["missing_tool_lease"] == "blocked"
    assert blocks_payload["audit_events"] >= 1
    assert blocks_payload["audit_record_created"] is True
    assert blocks_payload["raw_secret_present"] is False
    assert "sk-live-agent-fixture" not in blocks.stdout


def test_wave15_package_cli_outputs_eval_json() -> None:
    # Given: the package CLI is the user-visible Wave15 eval surface.
    env = local_src_tests_env()

    # When: Wave15 eval runs through python -m zeus_agent against local src/tests.
    payload = json.loads(
        subprocess.check_output(
            [
                sys.executable,
                "-m",
                "zeus_agent",
                "wave15-eval",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
        ),
    )

    # Then: eval reports Wave15 plus adjacent Wave12/Wave14 smoke status.
    assert payload["suite"] == "wave15"
    assert payload["failed"] == 0
    assert payload["wave12_adjacent_passed"] is True
    assert payload["wave14_adjacent_passed"] is True
    assert payload["live_production_claimed"] is False
    assert payload["no_live_network_opened"] is True
    assert any(
        check["name"] == "audit_record_created" and check["status"] == "pass"
        for check in payload["checks"]
    )
