from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_adapter_catalog_runtime import live_research_adapter_catalog_payload


def test_live_research_adapter_catalog_exposes_owned_clients_without_opening_network() -> None:
    payload = live_research_adapter_catalog_payload()
    adapter_ids = {adapter["adapter_id"] for adapter in payload["adapters"]}

    assert payload["adapter_count"] == 3
    assert payload["owned_client_adapter_count"] == 3
    assert payload["production_ready_count"] == 0
    assert adapter_ids == {"github", "web", "community"}
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False
    assert "ghp_" not in json.dumps(payload)


def test_live_research_adapter_catalog_records_guardrails_per_adapter() -> None:
    payload = live_research_adapter_catalog_payload()

    for adapter in payload["adapters"]:
        assert adapter["transport_runtime"] == "live_research_owned_client_transport"
        assert adapter["activation_policy_required"] is True
        assert adapter["approval_required"] is True
        assert adapter["source_pin_required"] is True
        assert adapter["production_fetcher_configured"] is False
        assert adapter["network_opened"] is False


def test_live_research_adapter_catalog_cli_and_library_surface_match() -> None:
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "live-research-adapters", "--json"],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    cli_payload = json.loads(proc.stdout)
    library_payload = ZeusAgent().live_research_adapters()
    assert cli_payload == library_payload
