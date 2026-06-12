from __future__ import annotations

import json
import os
import subprocess
import sys

from zeus_agent.plugin_runtime import validate_plugin_manifest

_VALID_MANIFEST = {
    "plugin_id": "zeus.sample_plugin",
    "name": "Sample Plugin",
    "version": "0.1.0",
    "entrypoint": "plugins/sample.py",
    "permissions": ["tool.register"],
    "dependencies": ["pydantic"],
    "sha256": "a" * 64,
}


def test_plugin_manifest_is_quarantined_until_review() -> None:
    result = validate_plugin_manifest(_VALID_MANIFEST)

    assert result.decision == "quarantined"
    assert result.reason == "plugin_candidate_quarantined"
    assert result.tool_registration_allowed is False
    assert result.handler_executed is False
    assert result.network_opened is False
    assert result.live_production_claimed is False
    assert result.manifest is not None
    assert result.manifest.plugin_id == "zeus.sample_plugin"


def test_plugin_manifest_blocks_unsafe_permissions_dependencies_and_secret_echo() -> None:
    raw_secret = "ghp_wave24_secret"
    result = validate_plugin_manifest(
        {
            "plugin_id": "zeus.unsafe_plugin",
            "name": "Unsafe Plugin",
            "version": "0.1.0",
            "entrypoint": "/tmp/unsafe.py",
            "permissions": ["tool.register", "credential.write", "live.network"],
            "dependencies": ["evil-package", raw_secret],
            "sha256": "not-a-hash",
        },
    )
    serialized = result.model_dump_json()

    assert result.decision == "blocked"
    assert "unsafe_permission" in result.blocked_reasons
    assert "untrusted_dependency" in result.blocked_reasons
    assert "invalid_sha256" in result.blocked_reasons
    assert "unsafe_entrypoint" in result.blocked_reasons
    assert raw_secret not in serialized
    assert result.tool_registration_allowed is False
    assert result.no_secret_echo is True


def test_plugin_validate_cli_reports_quarantine_without_activation() -> None:
    env = {**os.environ, "PYTHONPATH": "src"}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "zeus_agent",
            "plugin-validate",
            "--manifest-json",
            json.dumps(_VALID_MANIFEST, sort_keys=True),
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
    assert payload["decision"] == "quarantined"
    assert payload["tool_registration_allowed"] is False
    assert payload["live_production_claimed"] is False
