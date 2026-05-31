"""Controlled local process sandbox.

This is the first execution runtime. It is deliberately conservative: commands
only run after blueprint approval, receive a scrubbed environment, execute from
the approved workspace root, and are recorded as evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import subprocess
from typing import Iterable

from zeus_agent.paths import ensure_private_dir, sandboxes_dir
from zeus_agent.schemas.sandbox import FileFingerprint, SandboxCheckpoint, SandboxCommand, SandboxResult
from zeus_agent.schemas.trace_event import new_trace_event
from zeus_agent.security.path_guard import assert_path_under_roots
from zeus_agent.security.redaction import redact_text
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.jsonio import write_private_json
from zeus_agent.storage.run_store import RunStore

MAX_CAPTURE_CHARS = 20_000
DEFAULT_MAX_FILES = 1000
DEFAULT_MAX_BYTES = 10_000_000

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}

NETWORK_COMMANDS = {
    "curl",
    "wget",
    "ssh",
    "scp",
    "rsync",
    "nc",
    "ncat",
    "telnet",
    "ftp",
}

DESTRUCTIVE_COMMANDS = {
    "rm",
    "rmdir",
    "sudo",
    "chmod",
    "chown",
    "kill",
    "pkill",
    "launchctl",
}


class SandboxPolicyError(RuntimeError):
    """Raised when a command or path violates Zeus sandbox policy."""


def inventory_workspace(
    root: Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> tuple[list[FileFingerprint], list[str]]:
    root = root.expanduser().resolve()
    files: list[FileFingerprint] = []
    omitted: list[str] = []
    total_bytes = 0
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            if path.is_dir():
                omitted.append(f"{rel}/")
            continue
        if not path.is_file():
            continue
        if len(files) >= max_files:
            omitted.append(f"{rel}: omitted after max_files")
            continue
        try:
            stat = path.stat()
        except OSError as exc:
            omitted.append(f"{rel}: stat failed: {exc}")
            continue
        if total_bytes + stat.st_size > max_bytes:
            omitted.append(f"{rel}: omitted after max_bytes")
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            omitted.append(f"{rel}: read failed: {exc}")
            continue
        total_bytes += stat.st_size
        files.append(
            FileFingerprint(
                path=rel,
                size=stat.st_size,
                sha256=digest,
                modified_at=stat.st_mtime,
            )
        )
    return files, omitted


class SandboxRuntime:
    def __init__(self, home: Path | None = None) -> None:
        self.home = home
        self.store = RunStore(home)
        self.event_log = EventLog(home)

    def create_checkpoint(self, run_id: str) -> SandboxCheckpoint:
        contract, spec = self._approved_contract_and_spec(run_id)
        workspace_root = assert_path_under_roots(
            Path(spec.workspace.root),
            [Path(path) for path in contract.allowed_paths],
        )
        files, omitted = inventory_workspace(workspace_root)
        checkpoint = SandboxCheckpoint(
            run_id=run_id,
            workspace_root=str(workspace_root),
            file_count=len(files),
            total_bytes=sum(file.size for file in files),
            files=files,
            omitted=omitted,
        )
        artifact = self._checkpoint_path(run_id, checkpoint.checkpoint_id)
        write_private_json(artifact, checkpoint.model_dump(mode="json"))
        self.event_log.append(
            new_trace_event(
                "sandbox.checkpoint.created",
                run_id=run_id,
                payload={
                    "checkpoint_id": checkpoint.checkpoint_id,
                    "file_count": checkpoint.file_count,
                    "artifact": str(artifact),
                },
            )
        )
        return checkpoint

    def run_command(
        self,
        run_id: str,
        argv: Iterable[str],
        *,
        timeout_seconds: int | None = None,
    ) -> SandboxResult:
        contract, spec = self._approved_contract_and_spec(run_id)
        argv_list = [str(part) for part in argv if str(part)]
        if not argv_list:
            raise SandboxPolicyError("command argv must not be empty")
        workspace_root = assert_path_under_roots(
            Path(spec.workspace.root),
            [Path(path) for path in contract.allowed_paths],
        )
        self._validate_command(argv_list, spec.sandbox.network_policy)
        timeout = min(timeout_seconds or spec.budgets.max_wall_clock_seconds, spec.budgets.max_wall_clock_seconds)
        command = SandboxCommand(
            run_id=run_id,
            argv=argv_list,
            cwd=str(workspace_root),
            timeout_seconds=timeout,
            network_policy=spec.sandbox.network_policy,
            approved=True,
        )
        command_path = self._command_path(run_id, command.command_id)
        write_private_json(command_path, command.model_dump(mode="json"))
        started_at = datetime.now(UTC)
        try:
            completed = subprocess.run(
                argv_list,
                cwd=workspace_root,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self._safe_env(run_id),
                check=False,
            )
            stdout = completed.stdout[:MAX_CAPTURE_CHARS]
            stderr = completed.stderr[:MAX_CAPTURE_CHARS]
            timed_out = False
            exit_code: int | None = completed.returncode
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "")[:MAX_CAPTURE_CHARS] if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "")[:MAX_CAPTURE_CHARS] if isinstance(exc.stderr, str) else ""
            timed_out = True
            exit_code = None
        stdout_redacted = redact_text(stdout)
        stderr_redacted = redact_text(stderr)
        findings = sorted(set(stdout_redacted.findings + stderr_redacted.findings))
        result = SandboxResult(
            command_id=command.command_id,
            run_id=run_id,
            started_at=started_at,
            argv=argv_list,
            cwd=str(workspace_root),
            exit_code=exit_code,
            timed_out=timed_out,
            stdout=stdout_redacted.value,
            stderr=stderr_redacted.value,
            redaction_status="redacted" if findings else "clean",
            redaction_findings=findings,
        )
        result_path = self._result_path(run_id, result.result_id)
        result.artifact_path = str(result_path)
        write_private_json(result_path, result.model_dump(mode="json"))
        self.event_log.append(
            new_trace_event(
                "sandbox.command.finished",
                run_id=run_id,
                payload={
                    "command_id": command.command_id,
                    "result_id": result.result_id,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "artifact": str(result_path),
                },
            )
        )
        return result

    def _approved_contract_and_spec(self, run_id: str):
        contract = self.store.load_goal_contract(run_id)
        spec = self.store.load_execution_spec(run_id)
        if contract.approval_state != "approved" or spec.status not in {"approved", "ready"}:
            raise SandboxPolicyError("sandbox execution requires approved GoalContract and ExecutionSpec")
        return contract, spec

    def _validate_command(self, argv: list[str], network_policy: str) -> None:
        executable = Path(argv[0]).name
        lowered = [part.lower() for part in argv]
        if executable in DESTRUCTIVE_COMMANDS:
            raise SandboxPolicyError(f"destructive command is blocked: {executable}")
        if network_policy == "deny_by_default":
            if executable in NETWORK_COMMANDS:
                raise SandboxPolicyError(f"network command is blocked by policy: {executable}")
            if any(part.startswith(("http://", "https://", "git@")) for part in lowered):
                raise SandboxPolicyError("network-looking argument is blocked by deny-by-default policy")
        if len(argv) >= 2 and executable == "git" and argv[1] in {"push", "fetch", "pull", "clone"}:
            raise SandboxPolicyError(f"git {argv[1]} is blocked in the local process sandbox")

    def _safe_env(self, run_id: str) -> dict[str, str]:
        safe = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(self._sandbox_root(run_id)),
            "ZEUS_SANDBOX": "1",
            "ZEUS_RUN_ID": run_id,
        }
        for name in ("LANG", "LC_ALL", "TERM"):
            if name in os.environ:
                safe[name] = os.environ[name]
        return safe

    def _sandbox_root(self, run_id: str) -> Path:
        root = sandboxes_dir(self.store.home) / run_id
        ensure_private_dir(root)
        return root

    def _checkpoint_path(self, run_id: str, checkpoint_id: str) -> Path:
        path = self.store.artifacts_for(run_id).run_dir / "sandbox" / "checkpoints" / f"{checkpoint_id}.json"
        ensure_private_dir(path.parent)
        return path

    def _command_path(self, run_id: str, command_id: str) -> Path:
        path = self.store.artifacts_for(run_id).run_dir / "sandbox" / "commands" / f"{command_id}.json"
        ensure_private_dir(path.parent)
        return path

    def _result_path(self, run_id: str, result_id: str) -> Path:
        path = self.store.artifacts_for(run_id).run_dir / "sandbox" / "results" / f"{result_id}.json"
        ensure_private_dir(path.parent)
        return path
