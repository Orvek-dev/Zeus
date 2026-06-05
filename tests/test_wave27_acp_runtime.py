from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.acp_runtime import handle_acp_message


def test_acp_runtime_initializes_and_compiles_objective_without_write_authority() -> None:
    initialized = handle_acp_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    compiled = handle_acp_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "zeus.objective.compile",
            "params": {"objective": "Build a local governed coding plan."},
        },
    )

    assert initialized["result"]["name"] == "Zeus ACP"
    assert initialized["result"]["live_production_claimed"] is False
    assert compiled["result"]["status"] == "compiled"
    assert compiled["result"]["authority_posture"] == "plan_only"
    assert compiled["result"]["live_production_claimed"] is False


def test_acp_runtime_blocks_editor_write_methods_by_default() -> None:
    blocked = handle_acp_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "workspace.applyEdit",
            "params": {"path": "README.md"},
        },
    )

    assert blocked["error"]["code"] == -32001
    assert blocked["error"]["message"] == "acp_method_blocked"
    assert blocked["result"]["handler_executed"] is False
    assert blocked["result"]["live_production_claimed"] is False


def test_acp_handle_cli_returns_jsonrpc_response() -> None:
    env = {**os.environ, "PYTHONPATH": "src"}
    message = {"jsonrpc": "2.0", "id": 4, "method": "initialize"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "acp-handle",
            "--message-json",
            json.dumps(message),
            "--json",
        ],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["id"] == 4
    assert payload["result"]["name"] == "Zeus ACP"
