"""Mneme truth layer.

Mneme stores observable evidence: checkpoints, command results, diff gates, and
verification notes. Zeus can reason, but Mneme records what actually happened.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
import subprocess
from typing import Literal

from zeus_agent.runtime.sandbox import inventory_workspace
from zeus_agent.schemas.evidence import DiffGateReport, EvidenceRecord
from zeus_agent.schemas.sandbox import SandboxCheckpoint, SandboxResult
from zeus_agent.schemas.trace_event import new_trace_event
from zeus_agent.paths import ensure_private_dir
from zeus_agent.security.redaction import redact_data
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.jsonio import append_private_jsonl, read_json, write_private_json
from zeus_agent.storage.run_store import RunStore


EvidenceType = Literal["checkpoint", "command", "diff", "verification", "skill", "note"]


def record_evidence(
    run_id: str,
    evidence_type: EvidenceType,
    summary: str,
    *,
    artifact_paths: list[str] | None = None,
    passed: bool | None = None,
    payload: dict | None = None,
    home: Path | None = None,
) -> EvidenceRecord:
    store = RunStore(home)
    cleaned_payload, redacted, findings = redact_data(payload or {})
    record = EvidenceRecord(
        run_id=run_id,
        evidence_type=evidence_type,
        summary=summary,
        artifact_paths=artifact_paths or [],
        passed=passed,
        payload=cleaned_payload,
        redaction_status="redacted" if redacted else "clean",
        redaction_findings=list(findings),
    )
    append_private_jsonl(_evidence_path(store, run_id), record.model_dump(mode="json"))
    EventLog(home).append(
        new_trace_event(
            "mneme.evidence.recorded",
            run_id=run_id,
            payload={
                "evidence_id": record.evidence_id,
                "evidence_type": record.evidence_type,
                "passed": record.passed,
            },
        )
    )
    return record


def record_checkpoint_evidence(run_id: str, checkpoint: SandboxCheckpoint, *, home: Path | None = None) -> EvidenceRecord:
    return record_evidence(
        run_id,
        "checkpoint",
        f"Checkpoint {checkpoint.checkpoint_id} captured {checkpoint.file_count} files.",
        artifact_paths=[],
        passed=True,
        payload={
            "checkpoint_id": checkpoint.checkpoint_id,
            "file_count": checkpoint.file_count,
            "total_bytes": checkpoint.total_bytes,
            "omitted_count": len(checkpoint.omitted),
        },
        home=home,
    )


def record_command_evidence(run_id: str, result: SandboxResult, *, home: Path | None = None) -> EvidenceRecord:
    return record_evidence(
        run_id,
        "command",
        f"Command {' '.join(result.argv)} exited with {result.exit_code}.",
        artifact_paths=[result.artifact_path] if result.artifact_path else [],
        passed=(result.exit_code == 0 and not result.timed_out),
        payload={
            "command_id": result.command_id,
            "result_id": result.result_id,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
        },
        home=home,
    )


def list_evidence(run_id: str, *, home: Path | None = None) -> list[dict]:
    path = _evidence_path(RunStore(home), run_id)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def diff_gate(run_id: str, *, home: Path | None = None) -> DiffGateReport:
    store = RunStore(home)
    spec = store.load_execution_spec(run_id)
    workspace_root = Path(spec.workspace.root).expanduser().resolve()
    is_git_repo = (workspace_root / ".git").exists()
    changed_files = _git_changed_files(workspace_root) if is_git_repo else _checkpoint_changed_files(store, run_id, workspace_root)
    forbidden_hits = [
        path
        for path in changed_files
        if any(fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(str(workspace_root / path), pattern) for pattern in spec.workspace.forbidden_paths)
    ]
    requires_review = bool(changed_files)
    allowed = not forbidden_hits and (is_git_repo or _latest_checkpoint_path(store, run_id) is not None)
    summary = (
        "No changes detected."
        if not changed_files
        else f"{len(changed_files)} changed path(s) detected; {len(forbidden_hits)} forbidden hit(s)."
    )
    report = DiffGateReport(
        run_id=run_id,
        workspace_root=str(workspace_root),
        is_git_repo=is_git_repo,
        changed_files=changed_files,
        forbidden_path_hits=forbidden_hits,
        allowed=allowed,
        requires_human_review=requires_review,
        summary=summary,
    )
    artifact = _mneme_dir(store, run_id) / f"{report.report_id}.json"
    report.artifact_path = str(artifact)
    write_private_json(artifact, report.model_dump(mode="json"))
    record_evidence(
        run_id,
        "diff",
        summary,
        artifact_paths=[str(artifact)],
        passed=allowed,
        payload={"changed_files": changed_files, "forbidden_path_hits": forbidden_hits},
        home=home,
    )
    return report


def _git_changed_files(workspace_root: Path) -> list[str]:
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        check=False,
    )
    changed: list[str] = []
    for line in status.stdout.splitlines():
        if len(line) > 3:
            changed.append(line[3:].strip())
    return sorted(set(changed))


def _checkpoint_changed_files(store: RunStore, run_id: str, workspace_root: Path) -> list[str]:
    checkpoint_path = _latest_checkpoint_path(store, run_id)
    if checkpoint_path is None:
        return []
    checkpoint = SandboxCheckpoint.model_validate(read_json(checkpoint_path))
    before = {file.path: file.sha256 for file in checkpoint.files}
    after_files, _ = inventory_workspace(workspace_root)
    after = {file.path: file.sha256 for file in after_files}
    changed = set(before) ^ set(after)
    for path, digest in before.items():
        if path in after and after[path] != digest:
            changed.add(path)
    return sorted(changed)


def _latest_checkpoint_path(store: RunStore, run_id: str) -> Path | None:
    checkpoint_dir = store.artifacts_for(run_id).run_dir / "sandbox" / "checkpoints"
    if not checkpoint_dir.exists():
        return None
    checkpoints = sorted(checkpoint_dir.glob("checkpoint_*.json"), key=lambda path: path.stat().st_mtime)
    return checkpoints[-1] if checkpoints else None


def _mneme_dir(store: RunStore, run_id: str) -> Path:
    path = store.artifacts_for(run_id).run_dir / "mneme"
    return ensure_private_dir(path)


def _evidence_path(store: RunStore, run_id: str) -> Path:
    return _mneme_dir(store, run_id) / "evidence.jsonl"
