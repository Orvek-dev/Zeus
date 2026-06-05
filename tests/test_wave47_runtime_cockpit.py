from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.runtime_cockpit import RuntimeCockpitRuntime


def test_runtime_cockpit_reports_execution_backends_without_dispatch() -> None:
    # Given: the user asks for a Hermes-style execution backend cockpit.
    result = RuntimeCockpitRuntime().build()

    # Then: Zeus shows backend coverage while keeping all handlers closed.
    assert result.decision == "report"
    assert result.backend_count == 3
    assert result.planned_backend_count == 3
    assert result.blocked_backend_count == 0
    assert result.selected_backend is None
    assert "zeus runtime --backend terminal --json" in result.recommended_next_commands
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.live_production_claimed is False


def test_runtime_cockpit_inspects_terminal_backend() -> None:
    # Given: the user inspects the terminal dry-run planner backend.
    result = RuntimeCockpitRuntime().build(backend_id="terminal")

    # Then: Zeus returns a safe command plan without starting a process.
    assert result.decision == "report"
    assert result.selected_backend is not None
    assert result.selected_backend["backend_id"] == "terminal"
    assert result.selected_backend["decision"] == "planned"
    assert result.selected_backend["reason"] == "dry_run_plan_only"
    assert result.selected_backend["handler_executed"] is False
    assert result.selected_backend["network_opened"] is False


def test_runtime_cockpit_inspects_sandbox_backend() -> None:
    # Given: the user inspects the sandbox dry-run planner backend.
    result = RuntimeCockpitRuntime().build(backend_id="sandbox")

    # Then: Zeus exposes bounded sandbox obligations without executing commands.
    assert result.decision == "report"
    assert result.selected_backend is not None
    assert result.selected_backend["backend_id"] == "sandbox"
    assert result.selected_backend["decision"] == "planned"
    assert result.selected_backend["egress_policy"] == "none"
    assert result.selected_backend["cleanup_required"] is True
    assert result.selected_backend["handler_executed"] is False


def test_runtime_cockpit_blocks_unknown_backend_inspection() -> None:
    # Given: the user asks to inspect an unknown runtime backend id.
    result = RuntimeCockpitRuntime().build(backend_id="gpu")

    # Then: the cockpit fails closed instead of fabricating execution state.
    assert result.decision == "blocked"
    assert result.selected_backend is None
    assert result.blocked_reasons == ("unknown_runtime_backend",)
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_cli_exposes_runtime_cockpit_inspection() -> None:
    # Given: the user opens runtime cockpit inspection from CLI.
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "runtime", "--backend", "terminal", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    # Then: the CLI exposes terminal planning without side effects.
    assert payload["decision"] == "report"
    assert payload["selected_backend"]["backend_id"] == "terminal"
    assert payload["selected_backend"]["decision"] == "planned"
    assert payload["network_opened"] is False


def test_python_library_exposes_runtime_cockpit() -> None:
    # Given: a Python user wants runtime backend status.
    payload = ZeusAgent().runtime_status(backend_id="sandbox")

    # Then: the library returns the same JSON-compatible inspection.
    assert payload["decision"] == "report"
    assert payload["selected_backend"]["backend_id"] == "sandbox"
    assert payload["live_production_claimed"] is False
