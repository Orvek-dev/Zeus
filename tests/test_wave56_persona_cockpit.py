from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from zeus_agent import ZeusAgent
from zeus_agent.persona_cockpit_runtime import PersonaCockpitRuntime


def test_persona_cockpit_reports_zeus_identity_without_starting_chat(tmp_path: Path) -> None:
    result = PersonaCockpitRuntime(tmp_path).build()

    assert result.decision == "report"
    assert result.persona_id == "zeus"
    assert result.display_name == "Zeus"
    assert result.default_call_response == "Zeus is here."
    assert result.korean_call_response == "네, Zeus입니다."
    assert result.profile_count >= 7
    assert result.selected_profile is None
    assert "zeus persona --profile work --json" in result.recommended_next_commands
    assert result.chat_turn_started is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_persona_cockpit_inspects_objective_profile_boundary(tmp_path: Path) -> None:
    result = PersonaCockpitRuntime(tmp_path).build(profile="work")

    assert result.decision == "report"
    assert result.selected_profile is not None
    assert result.selected_profile["profile"] == "work"
    assert result.selected_profile["objective_mode_active"] is True
    assert result.selected_profile["authority_required_for_tools"] is True
    assert result.selected_profile["live_transport_default"] == "blocked"
    assert result.chat_turn_started is False


def test_persona_cockpit_inspects_chat_profile_boundary(tmp_path: Path) -> None:
    result = PersonaCockpitRuntime(tmp_path).build(profile="chat")

    assert result.selected_profile is not None
    assert result.selected_profile["profile"] == "chat"
    assert result.selected_profile["objective_mode_active"] is False
    assert result.selected_profile["authority_required_for_tools"] is True
    assert result.live_production_claimed is False


def test_persona_cockpit_blocks_unknown_profile(tmp_path: Path) -> None:
    result = PersonaCockpitRuntime(tmp_path).build(profile="unknown")

    assert result.decision == "blocked"
    assert result.selected_profile is None
    assert result.blocked_reasons == ("unknown_persona_profile",)
    assert result.chat_turn_started is False
    assert result.live_production_claimed is False


def test_cli_exposes_persona_cockpit(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "persona",
            "--home",
            str(tmp_path),
            "--profile",
            "work",
            "--json",
        ],
        check=True,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONPATH": "src"},
        text=True,
        capture_output=True,
    )
    payload = json.loads(completed.stdout)

    assert payload["decision"] == "report"
    assert payload["selected_profile"]["profile"] == "work"
    assert payload["selected_profile"]["objective_mode_active"] is True
    assert payload["chat_turn_started"] is False


def test_python_library_exposes_persona_cockpit(tmp_path: Path) -> None:
    payload = ZeusAgent(home=tmp_path).persona_status(profile="chat")

    assert payload["decision"] == "report"
    assert payload["persona_id"] == "zeus"
    assert payload["selected_profile"]["profile"] == "chat"
    assert payload["live_production_claimed"] is False
