from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from zeus_agent.eval.wave17 import run_wave17_eval

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


def test_wave17_eval_reports_mcp_manager_suite() -> None:
    # Given: Wave17 eval wraps MCP manager happy and blocked scenarios.
    payload = run_wave17_eval()

    # Then: all Wave17 checks pass without a production-live claim.
    assert payload["suite"] == "wave17"
    assert payload["failed"] == 0
    assert payload["mcp_manager_happy_passed"] is True
    assert payload["mcp_manager_blocks_passed"] is True
    assert payload["live_production_claimed"] is False


def test_wave17_package_cli_outputs_manager_json() -> None:
    # Given: package CLI commands expose Wave17 manager evidence.
    commands = (
        ("wave17-mcp-manager", "--scenario", "stdio-http"),
        ("wave17-mcp-manager-blocks", "--secret-like", "sk-wave17-cli-secret"),
        ("wave17-eval",),
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
    assert payloads[0]["manager_created"] is True
    assert payloads[1]["scenario_id"] == "C002"
    assert payloads[1]["raw_secret_present"] is False
    assert "sk-wave17-cli-secret" not in json.dumps(payloads, sort_keys=True)
    assert payloads[2]["suite"] == "wave17"
    assert payloads[2]["failed"] == 0
