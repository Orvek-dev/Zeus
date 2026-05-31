"""Content-addressed workspace checkpoints.

This is Zeus' restorable checkpoint layer. The first sandbox checkpoint already
records fingerprints; this store additionally saves file content once by
SHA-256 so a run can be restored without duplicating full workspace copies.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil

from zeus_agent.paths import checkpoints_dir, ensure_private_dir
from zeus_agent.runtime.sandbox_filters import IGNORED_DIRS, should_skip_path
from zeus_agent.schemas.checkpoint import RestoreReport, SnapshotFile, SnapshotManifest
from zeus_agent.schemas.trace_event import new_trace_event
from zeus_agent.security.path_guard import assert_path_under_roots
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.jsonio import read_json, write_private_json
from zeus_agent.storage.run_store import RunStore
from zeus_agent.storage.state import StateStore


class CheckpointStore:
    def __init__(self, home: Path | None = None) -> None:
        self.home = home
        self.run_store = RunStore(home)
        self.root = ensure_private_dir(checkpoints_dir(self.run_store.home))
        self.objects = ensure_private_dir(self.root / "objects")

    def capture(
        self,
        run_id: str,
        workspace_root: Path,
        *,
        max_files: int = 5000,
        max_bytes: int = 50_000_000,
    ) -> SnapshotManifest:
        workspace_root = workspace_root.expanduser().resolve()
        files: list[SnapshotFile] = []
        omitted: list[str] = []
        total = 0
        for path in sorted(workspace_root.rglob("*")):
            if should_skip_path(path, workspace_root):
                if path.is_dir():
                    omitted.append(f"{path.relative_to(workspace_root).as_posix()}/")
                continue
            if not path.is_file():
                continue
            if path.is_symlink():
                omitted.append(f"{path.relative_to(workspace_root).as_posix()}: symlink omitted")
                continue
            rel = path.relative_to(workspace_root).as_posix()
            if len(files) >= max_files:
                omitted.append(f"{rel}: omitted after max_files")
                continue
            try:
                stat = path.stat()
            except OSError as exc:
                omitted.append(f"{rel}: stat failed: {exc}")
                continue
            if total + stat.st_size > max_bytes:
                omitted.append(f"{rel}: omitted after max_bytes")
                continue
            try:
                data = path.read_bytes()
            except OSError as exc:
                omitted.append(f"{rel}: read failed: {exc}")
                continue
            digest = hashlib.sha256(data).hexdigest()
            _write_object(self.objects, digest, data)
            total += stat.st_size
            files.append(
                SnapshotFile(
                    path=rel,
                    size=stat.st_size,
                    sha256=digest,
                    mode=stat.st_mode & 0o777,
                    modified_at=stat.st_mtime,
                )
            )

        manifest = SnapshotManifest(
            run_id=run_id,
            workspace_root=str(workspace_root),
            files=files,
            omitted=omitted,
            object_store_root=str(self.objects),
        )
        path = self.manifest_path(run_id, manifest.snapshot_id)
        write_private_json(path, manifest.model_dump(mode="json"))
        StateStore(self.run_store.home).record_artifact(
            run_id,
            str(path),
            "checkpoint_manifest",
            {"snapshot_id": manifest.snapshot_id, "file_count": len(files), "ignored_dirs": sorted(IGNORED_DIRS)},
        )
        EventLog(self.run_store.home).append(
            new_trace_event(
                "checkpoint.snapshot.captured",
                run_id=run_id,
                payload={"snapshot_id": manifest.snapshot_id, "files": len(files), "artifact": str(path)},
            )
        )
        return manifest

    def restore(
        self,
        run_id: str,
        snapshot_id: str,
        *,
        allowed_roots: list[Path],
        prune_untracked: bool = False,
    ) -> RestoreReport:
        manifest = SnapshotManifest.model_validate(read_json(self.manifest_path(run_id, snapshot_id)))
        workspace_root = assert_path_under_roots(Path(manifest.workspace_root), allowed_roots)
        expected = {item.path for item in manifest.files}
        restored: list[str] = []
        skipped: list[str] = []

        for item in manifest.files:
            target = assert_path_under_roots(workspace_root / item.path, [workspace_root])
            source = _object_path(self.objects, item.sha256)
            if not source.exists():
                skipped.append(f"{item.path}: missing object")
                continue
            ensure_private_dir(target.parent)
            shutil.copyfile(source, target)
            try:
                os.chmod(target, item.mode)
            except PermissionError:
                pass
            restored.append(item.path)

        if prune_untracked:
            for path in sorted(workspace_root.rglob("*"), reverse=True):
                if should_skip_path(path, workspace_root) or not path.exists():
                    continue
                rel = path.relative_to(workspace_root).as_posix()
                if path.is_file() and rel not in expected:
                    path.unlink()
                elif path.is_dir():
                    try:
                        path.rmdir()
                    except OSError:
                        pass

        report = RestoreReport(
            run_id=run_id,
            snapshot_id=snapshot_id,
            restored_files=restored,
            skipped_files=skipped,
        )
        report_path = self.run_store.artifacts_for(run_id).run_dir / "sandbox" / "restores" / f"{report.restore_id}.json"
        write_private_json(report_path, report.model_dump(mode="json"))
        StateStore(self.run_store.home).record_artifact(
            run_id,
            str(report_path),
            "restore_report",
            {"snapshot_id": snapshot_id, "restored": len(restored), "skipped": len(skipped)},
        )
        EventLog(self.run_store.home).append(
            new_trace_event(
                "checkpoint.snapshot.restored",
                run_id=run_id,
                payload={
                    "snapshot_id": snapshot_id,
                    "restore_id": report.restore_id,
                    "restored": len(restored),
                    "skipped": len(skipped),
                },
            )
        )
        return report

    def manifest_path(self, run_id: str, snapshot_id: str) -> Path:
        path = self.run_store.artifacts_for(run_id).run_dir / "sandbox" / "snapshots" / f"{snapshot_id}.json"
        ensure_private_dir(path.parent)
        return path


def _write_object(root: Path, digest: str, data: bytes) -> Path:
    path = _object_path(root, digest)
    if path.exists():
        return path
    ensure_private_dir(path.parent)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    try:
        os.chmod(tmp, 0o600)
    except PermissionError:
        pass
    tmp.replace(path)
    return path


def _object_path(root: Path, digest: str) -> Path:
    return root / digest[:2] / digest
