from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.security_cockpit_runtime import SecurityCockpitRuntime


def test_security_cockpit_reports_aegis_controls_without_authority_widening() -> None:
    # Given: the user asks for Zeus Aegis security cockpit status.
    result = SecurityCockpitRuntime().build()

    # Then: Zeus reports controls and blocked reasons without opening transport.
    assert result.decision == "report"
    assert result.control_count == 4
    assert result.allowed_control_count == 2
    assert result.blocked_control_count == 2
    assert result.selected_control is None
    assert "zeus security --control-id lease-scope --json" in result.recommended_next_commands
    assert result.authority_widened is False
    assert result.network_opened is False
    assert result.handler_executed is False
    assert result.live_production_claimed is False


def test_security_cockpit_inspects_lease_scope_control() -> None:
    # Given: the user inspects a matching runtime lease control.
    result = SecurityCockpitRuntime().build(control_id="lease-scope")

    # Then: Zeus explains the dry-run authorization boundary.
    assert result.decision == "report"
    assert result.selected_control is not None
    assert result.selected_control["control_id"] == "lease-scope"
    assert result.selected_control["decision"] == "allowed"
    assert result.selected_control["reason"] == "dry_run"
    assert result.selected_control["scope_matched"] is True
    assert result.selected_control["network_opened"] is False


def test_security_cockpit_redacts_secret_scope_control() -> None:
    # Given: the user inspects the secret echo control.
    raw_secret = "sk-" + "wave49-secret"
    result = SecurityCockpitRuntime().build(control_id="secret-echo")
    serialized = json.dumps(result.to_payload(), sort_keys=True)

    # Then: Zeus blocks the unsafe scope and only exposes redacted evidence.
    assert result.decision == "report"
    assert result.selected_control is not None
    assert result.selected_control["decision"] == "blocked"
    assert result.selected_control["reason"] == "unsafe_credential_scope"
    assert result.selected_control["redacted_input"] == "sk-...redacted"
    assert raw_secret not in serialized
    assert result.no_secret_echo is True


def test_security_cockpit_blocks_unknown_control_inspection() -> None:
    # Given: the user asks to inspect an unknown security control.
    result = SecurityCockpitRuntime().build(control_id="unknown")

    # Then: the cockpit fails closed instead of inventing control status.
    assert result.decision == "blocked"
    assert result.selected_control is None
    assert result.blocked_reasons == ("unknown_security_control",)
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_cli_exposes_security_cockpit_inspection() -> None:
    # Given: the user opens security cockpit inspection from CLI.
    raw_secret = "sk-" + "wave49-secret"
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "security", "--control-id", "secret-echo", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    # Then: the CLI exposes redacted control evidence without raw secrets.
    assert payload["decision"] == "report"
    assert payload["selected_control"]["control_id"] == "secret-echo"
    assert payload["selected_control"]["redacted_input"] == "sk-...redacted"
    assert raw_secret not in completed.stdout


def test_python_library_exposes_security_cockpit() -> None:
    # Given: a Python user wants Aegis security status.
    payload = ZeusAgent().security_status(control_id="missing-lease")

    # Then: the library returns blocked security status without side effects.
    assert payload["decision"] == "report"
    assert payload["selected_control"]["control_id"] == "missing-lease"
    assert payload["selected_control"]["reason"] == "missing_runtime_lease"
    assert payload["live_production_claimed"] is False
