from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.model_settings_runtime import ModelSettingsRuntime
from zeus_agent.mcp_settings_runtime import McpSettingsRuntime
from zeus_agent.setup_runtime import setup_apply


def test_setup_apply_writes_model_and_mcp_local_config(tmp_path: Path) -> None:
    result = setup_apply(
        home=tmp_path,
        provider_id="openrouter/qwen",
        mcp=True,
        mcp_servers=("github",),
    )

    assert result["decision"] == "configured"
    assert result["settings_written"] is True
    assert result["model_settings"]["provider_id"] == "openrouter"
    assert result["model_settings"]["model_id"] == "openrouter/qwen"
    assert result["mcp_settings"]["configured_server_count"] == 1
    assert result["mcp_settings"]["configured_servers"][0]["state"] == "quarantined"
    assert result["network_opened"] is False
    assert result["credential_material_accessed"] is False
    assert result["live_production_claimed"] is False

    assert ModelSettingsRuntime(tmp_path).show().provider_id == "openrouter"
    assert McpSettingsRuntime(tmp_path).list().configured_server_count == 1


def test_setup_apply_blocks_unknown_provider_before_mcp_write(tmp_path: Path) -> None:
    result = setup_apply(
        home=tmp_path,
        provider_id="unknown-provider/model",
        mcp=True,
        mcp_servers=("github",),
    )

    assert result["decision"] == "blocked"
    assert "model:unknown_provider" in result["blocked_reasons"]
    assert result["settings_written"] is False
    assert McpSettingsRuntime(tmp_path).list().configured_server_count == 0
    assert result["live_production_claimed"] is False


def test_cli_setup_write_applies_local_first_run_config(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "setup",
            "--write",
            "--provider-id",
            "openrouter/qwen",
            "--mcp",
            "--mcp-server",
            "github",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["decision"] == "configured"
    assert payload["model_settings"]["provider_id"] == "openrouter"
    assert payload["mcp_settings"]["configured_server_count"] == 1
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def test_python_library_exposes_setup_apply(tmp_path: Path) -> None:
    payload = ZeusAgent(home=tmp_path).setup_apply(
        provider_id="local-llm",
        mcp=True,
        mcp_servers=("github",),
    )

    assert payload["decision"] == "configured"
    assert payload["model_settings"]["provider_id"] == "local-llm"
    assert payload["mcp_settings"]["configured_server_count"] == 1
    assert payload["live_production_claimed"] is False
