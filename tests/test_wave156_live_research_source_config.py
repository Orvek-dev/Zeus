from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_source_config_runtime import LiveResearchSourceConfigRuntime


def test_github_source_config_uses_default_endpoint_without_opening_network() -> None:
    result = LiveResearchSourceConfigRuntime().configure(adapter_id="github")
    payload = result.to_payload()

    assert payload["decision"] == "configured"
    assert payload["adapter_id"] == "github"
    assert payload["source_id"] == "github"
    assert payload["default_endpoint_used"] is True
    assert payload["endpoint"] == "https://api.github.com/search/repositories"
    assert payload["credential_scope"] == "external.github.readonly"
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def test_endpoint_required_adapters_block_without_endpoint_and_secret_echo() -> None:
    result = LiveResearchSourceConfigRuntime().configure(adapter_id="web")
    secret_result = LiveResearchSourceConfigRuntime().configure(
        adapter_id="community",
        endpoint="https://community.example.dev/search?token=ghp_" + "wave156",
    )
    serialized = json.dumps(secret_result.to_payload())

    assert result.decision == "blocked"
    assert "live_research_endpoint_required" in result.blocked_reasons
    assert secret_result.decision == "blocked"
    assert "live_research_endpoint_contains_secret" in secret_result.blocked_reasons
    assert "ghp_" + "wave156" not in serialized
    assert secret_result.no_secret_echo is True


def test_loopback_endpoint_requires_smoke_flag() -> None:
    blocked = LiveResearchSourceConfigRuntime().configure(
        adapter_id="web",
        endpoint="http://127.0.0.1:9123/search",
    )
    allowed = LiveResearchSourceConfigRuntime().configure(
        adapter_id="web",
        endpoint="http://127.0.0.1:9123/search",
        allow_loopback_smoke=True,
    )

    assert blocked.decision == "blocked"
    assert "live_research_loopback_endpoint_requires_smoke_flag" in blocked.blocked_reasons
    assert allowed.decision == "configured"
    assert allowed.loopback_endpoint is True
    assert allowed.non_loopback_endpoint is False
    assert allowed.network_opened is False


def test_source_config_cli_and_library_surface_match() -> None:
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "live-research-source-config",
            "--adapter-id",
            "web",
            "--endpoint",
            "https://search.example.dev/query",
            "--json",
        ],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    cli_payload = json.loads(proc.stdout)
    library_payload = ZeusAgent().live_research_source_config(
        adapter_id="web",
        endpoint="https://search.example.dev/query",
    )
    assert cli_payload == library_payload
