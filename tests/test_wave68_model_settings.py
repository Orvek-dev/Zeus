from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.entry_runtime import ZeusChatRuntime
from zeus_agent.model_settings_runtime import ModelSettingsRuntime


def test_model_settings_store_openrouter_slash_ref_locally(tmp_path: Path) -> None:
    result = ModelSettingsRuntime(tmp_path).set(provider_ref="openrouter/qwen")

    assert result.decision == "configured"
    assert result.provider_id == "openrouter"
    assert result.model_id == "openrouter/qwen"
    assert result.source == "configured"
    assert result.requires_credential is True
    assert result.requires_network_lease is True
    assert result.network_opened is False
    assert result.credential_material_accessed is False
    assert result.live_production_claimed is False

    shown = ModelSettingsRuntime(tmp_path).show()
    assert shown.provider_id == "openrouter"
    assert shown.model_id == "openrouter/qwen"
    assert shown.source == "configured"


def test_model_settings_blocks_unknown_provider_without_overwriting_default(tmp_path: Path) -> None:
    runtime = ModelSettingsRuntime(tmp_path)

    blocked = runtime.set(provider_ref="unknown-provider/model")
    shown = runtime.show()

    assert blocked.decision == "blocked"
    assert blocked.blocked_reasons == ("unknown_provider",)
    assert shown.provider_id == "fake"
    assert shown.model_id == "fake.zeus"
    assert shown.source == "default"
    assert shown.live_production_claimed is False


def test_chat_default_uses_saved_model_preference_without_live_transport(tmp_path: Path) -> None:
    ModelSettingsRuntime(tmp_path).set(provider_ref="local-llm", model_id="local.custom")

    result = ZeusChatRuntime(tmp_path).run_turn(message="hello Zeus")

    assert result.provider_id == "local-llm"
    assert result.model_id == "local.custom"
    assert result.objective_mode_active is False
    assert result.live_production_claimed is False


def test_cli_model_set_and_show_config(tmp_path: Path) -> None:
    runner = CliRunner()

    configured = runner.invoke(
        app,
        ["model", "--set", "openrouter/qwen", "--home", str(tmp_path), "--json"],
    )
    shown = runner.invoke(
        app,
        ["model", "--show-config", "--home", str(tmp_path), "--json"],
    )
    chat = runner.invoke(
        app,
        ["chat", "--message", "hello Zeus", "--home", str(tmp_path), "--json"],
    )

    assert configured.exit_code == 0, configured.stdout
    assert shown.exit_code == 0, shown.stdout
    assert chat.exit_code == 0, chat.stdout
    configured_payload = json.loads(configured.stdout)
    shown_payload = json.loads(shown.stdout)
    chat_payload = json.loads(chat.stdout)
    assert configured_payload["decision"] == "configured"
    assert shown_payload["provider_id"] == "openrouter"
    assert shown_payload["model_id"] == "openrouter/qwen"
    assert chat_payload["provider_id"] == "openrouter"
    assert chat_payload["model_id"] == "openrouter/qwen"
    assert chat_payload["live_production_claimed"] is False


def test_python_library_exposes_model_set_and_preference(tmp_path: Path) -> None:
    agent = ZeusAgent(home=tmp_path)

    configured = agent.model_set(provider_ref="local-llm", model_id="local.custom")
    shown = agent.model_preference()
    chat = agent.chat("hello Zeus")

    assert configured["decision"] == "configured"
    assert shown["provider_id"] == "local-llm"
    assert shown["model_id"] == "local.custom"
    assert chat["provider_id"] == "local-llm"
    assert chat["model_id"] == "local.custom"
    assert chat["live_production_claimed"] is False
