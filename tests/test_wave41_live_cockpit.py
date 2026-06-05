from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime


def test_live_cockpit_reports_default_readiness_without_running_smoke() -> None:
    # Given: a user asks Zeus for the live platform cockpit without opt-in smoke.
    result = LiveCockpitRuntime().build()

    # Then: Zeus summarizes readiness without opening live side effects.
    assert result.decision == "report"
    assert result.profile == "live"
    assert result.optin_smoke is None
    assert result.surface_count >= 10
    assert result.live_beta_count == 0
    assert "zeus live --include-smoke --scenario happy" in result.recommended_next_commands
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.live_production_claimed is False


def test_live_cockpit_absorbs_happy_optin_smoke_as_beta_only() -> None:
    # Given: the operator includes the fake opt-in smoke bundle.
    result = LiveCockpitRuntime().build(include_smoke=True, scenario="happy")

    # Then: the cockpit shows beta readiness while preserving production boundary.
    assert result.decision == "report"
    assert result.optin_smoke is not None
    assert result.optin_smoke.decision == "passed"
    assert result.live_beta_count == 2
    assert result.blocked_reasons == ()
    assert result.live_production_claimed is False
    assert result.external_delivery_opened is False


def test_live_cockpit_surfaces_blocked_optin_reasons() -> None:
    # Given: the opt-in smoke is run through a blocked scenario.
    result = LiveCockpitRuntime().build(include_smoke=True, scenario="blocked")

    # Then: Zeus carries the blocked reasons into the cockpit instead of hiding them.
    assert result.decision == "blocked"
    assert result.optin_smoke is not None
    assert "provider:missing_approval" in result.blocked_reasons
    assert "gateway:delivery_target_not_allowlisted" in result.blocked_reasons
    assert result.network_opened is False
    assert result.no_secret_echo is True


def test_cli_exposes_live_cockpit_with_smoke() -> None:
    # Given: the user opens the live cockpit from CLI.
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "live", "--include-smoke", "--scenario", "happy", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    # Then: CLI output summarizes beta live readiness without production claims.
    assert payload["decision"] == "report"
    assert payload["profile"] == "live"
    assert payload["optin_smoke"]["decision"] == "passed"
    assert payload["live_beta_count"] == 2
    assert payload["live_production_claimed"] is False


def test_python_library_exposes_live_cockpit() -> None:
    # Given: a Python user asks for the live cockpit.
    payload = ZeusAgent().live_status(include_smoke=True)

    # Then: the library returns the same JSON-compatible live status.
    assert payload["decision"] == "report"
    assert payload["profile"] == "live"
    assert payload["optin_smoke"]["decision"] == "passed"
    assert payload["live_beta_count"] == 2
