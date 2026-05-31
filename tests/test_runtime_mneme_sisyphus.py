import sys

import pytest

from zeus_agent.core.approvals import approve_run
from zeus_agent.core.blueprint import build_blueprint
from zeus_agent.core.mneme import diff_gate, list_evidence, record_command_evidence
from zeus_agent.core.sisyphus import pursue_run
from zeus_agent.runtime.sandbox import SandboxPolicyError, SandboxRuntime
from zeus_agent.storage.run_store import RunStore


def _approved_run(tmp_path):
    home = tmp_path / "zeus-home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "README.md").write_text("# demo\n", encoding="utf-8")
    bundle = build_blueprint("Create a local implementation plan", workspace=workspace)
    store = RunStore(home)
    store.save_blueprint(bundle.goal_contract, bundle.execution_spec)
    approve_run(bundle.execution_spec.run_id, home=home)
    return home, workspace, bundle.execution_spec.run_id


def test_sandbox_checkpoint_and_command_record_evidence(tmp_path):
    home, _, run_id = _approved_run(tmp_path)
    runtime = SandboxRuntime(home)

    checkpoint = runtime.create_checkpoint(run_id)
    result = runtime.run_command(run_id, [sys.executable, "-c", "print('sandbox-ok')"])
    evidence = record_command_evidence(run_id, result, home=home)

    assert checkpoint.file_count == 1
    assert result.exit_code == 0
    assert "sandbox-ok" in result.stdout
    assert evidence.passed is True
    assert list_evidence(run_id, home=home)


def test_sandbox_blocks_network_commands(tmp_path):
    home, _, run_id = _approved_run(tmp_path)

    with pytest.raises(SandboxPolicyError):
        SandboxRuntime(home).run_command(run_id, ["curl", "https://example.com"])


def test_mneme_diff_gate_detects_checkpoint_changes(tmp_path):
    home, workspace, run_id = _approved_run(tmp_path)
    SandboxRuntime(home).create_checkpoint(run_id)
    (workspace / "new.txt").write_text("changed\n", encoding="utf-8")

    report = diff_gate(run_id, home=home)

    assert report.allowed is True
    assert report.requires_human_review is True
    assert "new.txt" in report.changed_files


def test_sisyphus_pursue_records_escalation_report(tmp_path):
    home, _, run_id = _approved_run(tmp_path)

    report = pursue_run(run_id, home=home)

    assert report.status == "escalated"
    assert report.progress_score > 0
    assert report.artifact_paths
    assert report.escalation_reasons
