from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from zeus_agent.eval.wave18 import run_wave18_eval

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = PROJECT_ROOT / "src"


def local_src_env() -> dict[str, str]:
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(LOCAL_SRC)
        if not current_pythonpath
        else os.pathsep.join((str(LOCAL_SRC), current_pythonpath))
    )
    return env


def test_wave18_eval_reports_tool_sandbox_suite() -> None:
    # Given: Wave18 eval wraps tool sandbox happy and block scenarios.
    payload = run_wave18_eval()

    # Then: all checks pass without a production-live claim.
    assert payload["suite"] == "wave18"
    assert payload["failed"] == 0
    assert payload["tool_sandbox_happy_passed"] is True
    assert payload["tool_sandbox_blocks_passed"] is True
    assert payload["live_production_claimed"] is False


def test_wave18_package_cli_outputs_tool_sandbox_json() -> None:
    # Given: package CLI commands expose Wave18 tool sandbox evidence.
    commands = (
        ("wave18-tool-sandbox", "--scenario", "local-safe"),
        ("wave18-tool-sandbox-blocks", "--secret-like", "sk-wave18-cli-secret"),
        ("wave18-eval",),
    )

    # When: each command is invoked through python -m zeus_agent against local src.
    payloads = [
        json.loads(
            subprocess.check_output(
                ["python3", "-m", "zeus_agent", *command, "--json"],
                cwd=PROJECT_ROOT,
                env=local_src_env(),
                text=True,
            ),
        )
        for command in commands
    ]

    # Then: CLI output is structured and secret-safe.
    assert payloads[0]["scenario_id"] == "C001"
    assert payloads[0]["sandbox_executor_created"] is True
    assert payloads[1]["scenario_id"] == "C002"
    assert payloads[1]["raw_secret_present"] is False
    assert "sk-wave18-cli-secret" not in json.dumps(payloads, sort_keys=True)
    assert payloads[2]["suite"] == "wave18"
    assert payloads[2]["failed"] == 0
