from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent import ZeusAgent
from zeus_agent.model_cockpit_runtime import ModelCockpitRuntime


def test_model_cockpit_reports_provider_breadth_without_live_claim() -> None:
    # Given: the user asks for model/provider cockpit overview.
    result = ModelCockpitRuntime().build()

    # Then: Zeus exposes provider breadth without opening provider transport.
    assert result.decision == "report"
    assert result.provider_profile_count == 16
    assert result.local_first_count >= 4
    assert "openai_compatible" in result.api_modes
    assert result.selected_provider is None
    assert "zeus model --provider-id openai --json" in result.recommended_next_commands
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False


def test_model_cockpit_inspects_external_provider_requirements() -> None:
    # Given: the user inspects an external provider profile.
    result = ModelCockpitRuntime().build(provider_id="openai")

    # Then: Zeus shows credential/network requirements without accessing them.
    assert result.decision == "report"
    assert result.selected_provider is not None
    assert result.selected_provider["provider_id"] == "openai"
    assert result.selected_provider["display_name"] == "OpenAI"
    assert result.selected_provider["requires_credential"] is True
    assert result.selected_provider["requires_network_lease"] is True
    assert result.network_opened is False
    assert result.credential_material_accessed is False


def test_model_cockpit_inspects_local_provider_as_local_first() -> None:
    # Given: the user inspects a local-first model profile.
    result = ModelCockpitRuntime().build(provider_id="local-llm")

    # Then: Zeus marks it as local-first and credential-free.
    assert result.decision == "report"
    assert result.selected_provider is not None
    assert result.selected_provider["local_first"] is True
    assert result.selected_provider["requires_credential"] is False
    assert result.selected_provider["requires_network_lease"] is False


def test_model_cockpit_blocks_unknown_provider() -> None:
    # Given: the user asks for an unknown provider id.
    result = ModelCockpitRuntime().build(provider_id="unknown-provider")

    # Then: Zeus fails closed instead of inventing provider state.
    assert result.decision == "blocked"
    assert result.selected_provider is None
    assert result.blocked_reasons == ("unknown_provider",)
    assert result.live_production_claimed is False


def test_cli_exposes_model_cockpit() -> None:
    # Given: the user opens model cockpit inspection from CLI.
    completed = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "model", "--provider-id", "openai", "--json"],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    # Then: the CLI exposes provider requirements without side effects.
    assert payload["decision"] == "report"
    assert payload["selected_provider"]["provider_id"] == "openai"
    assert payload["selected_provider"]["requires_credential"] is True
    assert payload["network_opened"] is False


def test_python_library_exposes_model_cockpit() -> None:
    # Given: a Python user wants provider status.
    payload = ZeusAgent().model_status(provider_id="openai")

    # Then: the library returns the same JSON-compatible provider inspection.
    assert payload["decision"] == "report"
    assert payload["selected_provider"]["display_name"] == "OpenAI"
    assert payload["live_production_claimed"] is False
