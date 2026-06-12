from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from zeus_agent.eval.wave11 import run_wave11_eval
from zeus_agent.wave11_tool_scenarios import (
    wave11_tool_mcp_blocks_payload,
    wave11_tool_mcp_happy_payload,
)

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


def test_wave11_scenario_payloads_match_ulw_criteria() -> None:
    # Given: Wave11 happy and blocked scenario payload builders.
    happy = wave11_tool_mcp_happy_payload()
    blocked = wave11_tool_mcp_blocks_payload(
        raw_secret="ghp_TEST_FIXTURE",
    )

    # When: their observable fields are evaluated against the ULW criteria.
    required_happy = (
        "tool_registry_compiled",
        "toolset_enabled",
        "toolset_disabled_hidden",
        "mcp_discovery_normalized",
        "model_visible_schema_count>=2",
        "local_tool_schema_visible",
        "mcp_tool_schema_visible",
        "broker_dispatch_allowed",
        "mcp_dispatch_allowed",
        "runtime_lease_validated",
        "transport_registry_allowed",
        "result_redacted",
        "handler_executed",
        "no_secret_echo",
    )
    required_blocks = (
        "schema_injection_redacted",
        "raw_secret_result_redacted",
        "no_secret_echo",
    )

    # Then: every positive field is true and dangerous side effects remain closed.
    assert all(happy[field] is True for field in required_happy)
    assert happy["network_opened"] is False
    assert happy["credential_material_accessed"] is False
    assert happy["model_visible_schema_count"] >= 2
    assert blocked["missing_runtime_lease"] == "blocked"
    assert blocked["expired_runtime_lease"] == "blocked"
    assert blocked["disabled_toolset"] == "blocked"
    assert blocked["unknown_tool"] == "blocked"
    assert blocked["malformed_mcp_discovery"] == "blocked"
    assert blocked["malformed_tool_arguments"] == "blocked"
    assert blocked["capability_widening"] == "blocked"
    assert blocked["transport_mismatch"] == "blocked"
    assert blocked["unhealthy_transport"] == "blocked"
    assert blocked["over_budget"] == "blocked"
    assert all(blocked[field] is True for field in required_blocks)
    assert blocked["handler_executed"] is False
    assert blocked["client_constructed"] is False
    assert blocked["network_opened"] is False
    assert blocked["credential_material_accessed"] is False
    assert blocked["raw_secret_present"] is False


def test_wave11_eval_passes_all_checks() -> None:
    # Given: the Wave11 eval suite wraps happy, blocked, and redaction criteria.
    payload = run_wave11_eval()

    # When: the eval summary is inspected.
    checks = payload["checks"]

    # Then: every Wave11 check passes.
    assert payload["suite"] == "wave11"
    assert payload["total"] >= 1
    assert payload["failed"] == 0
    assert isinstance(checks, list)
    assert {check["status"] for check in checks} == {"pass"}


def test_wave11_cli_smoke_outputs_json() -> None:
    # Given: the package CLI is the user-visible Wave11 surface.
    commands = (
        ("wave11-tools",),
        ("wave11-blocks", "--secret-like", "ghp_TEST_FIXTURE"),
        ("wave11-eval",),
    )
    env = local_src_env()

    # When: each command is invoked through python -m zeus_agent against local src.
    payloads = [
        json.loads(
            subprocess.check_output(
                ["python3", "-m", "zeus_agent", *command, "--json"],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
            ),
        )
        for command in commands
    ]

    # Then: the CLI exposes happy, edge, and eval evidence without side effects.
    assert payloads[0]["scenario_id"] == "C001"
    assert payloads[0]["tool_registry_compiled"] is True
    assert payloads[1]["scenario_id"] == "C002"
    assert payloads[1]["missing_runtime_lease"] == "blocked"
    assert payloads[1]["raw_secret_present"] is False
    assert payloads[2]["suite"] == "wave11"
    assert payloads[2]["failed"] == 0
