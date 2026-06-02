from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from zeus_agent.eval.wave12 import run_wave12_eval

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = PROJECT_ROOT / "src"
LOCAL_TESTS = PROJECT_ROOT / "tests"


def local_src_tests_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join((str(LOCAL_SRC), str(LOCAL_TESTS)))
    return env


def test_wave12_cli_happy_and_blocks_output_json(tmp_path: Path) -> None:
    # Given: the package CLI is the user-visible Wave12 surface.
    env = local_src_tests_env()
    commands = (
        (
            "wave12-chat",
            "--message",
            "Inspect repo, call echo tool, summarize evidence",
            "--home",
            str(tmp_path / "state"),
            "--json",
        ),
        (
            "wave12-blocks",
            "--secret-like",
            "ghp_TEST_FIXTURE",
            "--json",
        ),
    )

    # When: happy and block commands run through python -m zeus_agent.
    payloads = [
        json.loads(
            subprocess.check_output(
                ["python3", "-m", "zeus_agent", *command],
                cwd=PROJECT_ROOT,
                env=env,
                text=True,
            ),
        )
        for command in commands
    ]

    # Then: the CLI exposes C001/C002 without network or secret leakage.
    assert payloads[0]["scenario_id"] == "C001"
    assert payloads[0]["conversation_runtime_created"] is True
    assert payloads[0]["provider_invoked"] is True
    assert payloads[0]["tool_schema_compiled"] is True
    assert payloads[0]["verification_completion_allowed"] is True
    assert payloads[0]["network_opened"] is False
    assert payloads[1]["scenario_id"] == "C002"
    assert payloads[1]["empty_message"] == "blocked"
    assert payloads[1]["missing_runtime_lease"] == "blocked"
    assert payloads[1]["provider_fallback_recorded"] is True
    assert payloads[1]["raw_secret_present"] is False


def test_wave12_eval_passes_required_suite() -> None:
    # Given: the Wave12 eval suite wraps provider, tool, verification, and CLI smoke.
    payload = run_wave12_eval()

    # When: the eval summary is inspected.
    checks = payload["checks"]

    # Then: every Wave12 and adjacent-surface check passes.
    assert payload["suite"] == "wave12"
    assert payload["failed"] == 0
    assert payload["wave10_provider_eval_passed"] is True
    assert payload["wave11_tool_eval_passed"] is True
    assert payload["verification_engine_gate_passed"] is True
    assert payload["cli_eval_smoke_success"] is True
    assert payload["adjacent_surface_still_works"] is True
    assert isinstance(checks, list)
    assert {check["status"] for check in checks} == {"pass"}
