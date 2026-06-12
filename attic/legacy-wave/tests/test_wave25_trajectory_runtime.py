from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.trajectory_runtime import export_trajectory


def test_trajectory_export_redacts_secret_material_and_preserves_order() -> None:
    raw_secret = "sk-wave25-secret"
    export = export_trajectory(
        run_id="wave25.run",
        events=(
            {"step": "provider", "content": f"token={raw_secret}"},
            {"step": "tool", "content": "handler_executed=false"},
        ),
    )
    serialized = export.model_dump_json()

    assert export.run_id == "wave25.run"
    assert export.event_count == 2
    assert export.events[0]["step"] == "provider"
    assert "[redacted-secret]" in serialized
    assert raw_secret not in serialized
    assert export.live_production_claimed is False


def test_trajectory_export_cli_returns_redacted_payload() -> None:
    env = {**os.environ, "PYTHONPATH": "src"}
    events = [{"step": "api", "content": "response stored"}]
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "trajectory-export",
            "--run-id",
            "wave25.run.cli",
            "--events-json",
            json.dumps(events),
            "--json",
        ],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["run_id"] == "wave25.run.cli"
    assert payload["event_count"] == 1
    assert payload["live_production_claimed"] is False
