from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import typer
from typer.testing import CliRunner

from zeus_agent.cli_wave14 import register_wave14_commands

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = PROJECT_ROOT / "src"
LOCAL_TESTS = PROJECT_ROOT / "tests"


def local_src_tests_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(LOCAL_SRC), str(LOCAL_TESTS)))
    return env


def test_wave14_cli_registration_outputs_plan_and_block_json(
    tmp_path: Path,
) -> None:
    # Given: an isolated Typer app using Wave14 command registration only.
    app = typer.Typer()
    register_wave14_commands(app)
    runner = CliRunner()
    home = tmp_path / "wave14-state"

    # When: live plan and block commands run through the local CLI surface.
    plan = runner.invoke(
        app,
        ["wave14-live-plan", "--scenario", "full-dry-run", "--home", str(home), "--json"],
    )
    blocks = runner.invoke(
        app,
        [
            "wave14-live-blocks",
            "--secret-like",
            "sk-wave14-secret",
            "--home",
            str(home),
            "--json",
        ],
    )
    orchestra = runner.invoke(
        app,
        [
            "wave14-orchestra-plan",
            "--scenario",
            "parallel-dry-run",
            "--home",
            str(home),
            "--json",
        ],
    )

    # Then: both commands emit the requested JSON contracts without secret echo.
    assert plan.exit_code == 0, plan.stdout
    assert blocks.exit_code == 0, blocks.stdout
    assert orchestra.exit_code == 0, orchestra.stdout
    plan_payload = json.loads(plan.stdout)
    blocks_payload = json.loads(blocks.stdout)
    orchestra_payload = json.loads(orchestra.stdout)
    assert plan_payload["decision"] == "planned"
    assert plan_payload["network_opened"] is False
    assert plan_payload["live_production_claimed"] is False
    assert blocks_payload["raw_secret_present"] is False
    assert orchestra_payload["orchestra_decision"] == "planned"
    assert orchestra_payload["live_production_claimed"] is False
    assert "sk-wave14-secret" not in blocks.stdout


def test_wave14_package_cli_outputs_eval_json() -> None:
    # Given: the package CLI is the user-visible Wave14 surface.
    env = local_src_tests_env()

    # When: Wave14 eval runs through python -m zeus_agent against local src/tests.
    payload = json.loads(
        subprocess.check_output(
            [
                sys.executable,
                "-m",
                "zeus_agent",
                "wave14-eval",
                "--json",
            ],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
        ),
    )

    # Then: the registered package CLI emits the ULW regression fields.
    assert payload["suite"] == "wave14"
    assert payload["failed"] == 0
    assert payload["adjacent_surface_still_works"] is True
    assert payload["live_production_claimed"] is False
