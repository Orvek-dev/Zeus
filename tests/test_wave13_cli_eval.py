from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path

import typer
from typer.testing import CliRunner

from zeus_agent.cli_wave13 import register_wave13_commands
from zeus_agent.eval.wave13 import run_wave13_eval

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = PROJECT_ROOT / "src"
LOCAL_TESTS = PROJECT_ROOT / "tests"


def local_src_tests_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(LOCAL_SRC), str(LOCAL_TESTS)))
    return env


def test_wave13_cli_registration_outputs_production_and_block_json(
    tmp_path: Path,
) -> None:
    # Given: an isolated Typer app using Wave13 command registration only.
    app = typer.Typer()
    register_wave13_commands(app)
    runner = CliRunner()
    home = tmp_path / "wave13-state"

    # When: production and block commands run through the local CLI surface.
    production = runner.invoke(app, ["wave13-production", "--home", str(home), "--json"])
    blocks = runner.invoke(
        app,
        [
            "wave13-blocks",
            "--secret-like",
            "sk-wave13-secret",
            "--home",
            str(home),
            "--json",
        ],
    )

    # Then: both commands emit the requested JSON contracts without secret echo.
    assert production.exit_code == 0, production.stdout
    assert blocks.exit_code == 0, blocks.stdout
    production_payload = json.loads(production.stdout)
    blocks_payload = json.loads(blocks.stdout)
    assert production_payload["gateway_draft_created"] is True
    assert production_payload["network_opened"] is False
    assert blocks_payload["gateway_without_lease"] == "blocked"
    assert blocks_payload["raw_secret_present"] is False
    assert "sk-wave13-secret" not in blocks.stdout


def test_wave13_package_cli_outputs_eval_json() -> None:
    # Given: the package CLI is the user-visible Wave13 surface.
    env = local_src_tests_env()

    # When: Wave13 eval runs through python -m zeus_agent against local src/tests.
    payload = json.loads(
        subprocess.check_output(
            ["python3", "-m", "zeus_agent", "wave13-eval", "--json"],
            cwd=PROJECT_ROOT,
            env=env,
            text=True,
        ),
    )

    # Then: the registered package CLI emits the ULW regression fields.
    assert payload["suite"] == "wave13"
    assert payload["failed"] == 0
    assert payload["wave12_eval_passed"] is True
    assert payload["wave9_lease_eval_passed"] is True
    assert payload["wave10_provider_eval_passed"] is True
    assert payload["wave11_tool_eval_passed"] is True
    assert payload["final_architecture_eval_passed"] is True
    assert payload["adjacent_surface_still_works"] is True
    assert payload["governance_gates_ok"] is True


def test_wave13_eval_reports_local_suite_and_adjacent_importable_smokes() -> None:
    # Given: the Wave13 eval wraps local criteria and adjacent regression evals.
    wave12_available = importlib.util.find_spec("zeus_agent.eval.wave12") is not None

    # When: the eval function is run directly.
    payload = run_wave13_eval()

    # Then: Wave13 passes locally and reports importable adjacent evals.
    assert payload["suite"] == "wave13"
    assert payload["failed"] == 0
    assert payload["wave13_eval_total"] >= 1
    assert payload["wave13_eval_failed"] == 0
    assert payload["wave9_eval_passed"] is True
    assert payload["wave9_lease_eval_passed"] is True
    assert payload["wave10_eval_passed"] is True
    assert payload["wave10_provider_eval_passed"] is True
    assert payload["wave11_eval_passed"] is True
    assert payload["wave11_tool_eval_passed"] is True
    assert payload["final_eval_passed"] is True
    assert payload["final_architecture_eval_passed"] is True
    assert payload["governance_gates_ok"] is True
    assert payload["adjacent_surface_still_works"] is True
    if wave12_available:
        assert payload["wave12_eval_passed"] is True
    else:
        assert payload["wave12_eval_available"] is False
