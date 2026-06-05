from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app


def test_chat_command_defaults_to_hermes_compatible_zeus_persona(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "chat",
            "--message",
            "hello Zeus",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["session_id"] == "default"
    assert payload["profile"] == "chat"
    assert payload["provider_id"] == "fake"
    assert payload["assistant_message"].startswith("Zeus is here")
    assert payload["objective_mode_active"] is False
    assert payload["live_production_claimed"] is False


def test_chat_command_preserves_wave3_fake_tool_loop_when_scenario_is_explicit(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "chat",
            "--message",
            "find needle but hide sk-chat-secret",
            "--scenario",
            "fake-search",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    blob = json.dumps(payload, sort_keys=True)
    assert payload["mode"] == "chat"
    assert payload["fake_local_only"] is True
    assert payload["broker_decision"]["capability_id"] == "text.search"
    assert "sk-chat-secret" not in blob


def test_chat_command_can_select_work_profile_without_live_authority(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "chat",
            "--message",
            "이 repo 구현 작업을 진행해",
            "--profile",
            "work",
            "--session-id",
            "wave66",
            "--home",
            str(tmp_path),
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["session_id"] == "wave66"
    assert payload["profile"] == "work"
    assert payload["objective_mode_active"] is True
    assert payload["live_production_claimed"] is False


def test_python_library_chat_keeps_same_light_default(tmp_path: Path) -> None:
    payload = ZeusAgent(home=tmp_path).chat("hello Zeus")

    assert payload["profile"] == "chat"
    assert payload["assistant_message"].startswith("Zeus is here")
    assert payload["objective_mode_active"] is False
    assert payload["live_production_claimed"] is False
