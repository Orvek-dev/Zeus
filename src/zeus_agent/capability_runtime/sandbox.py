from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Sequence

DEFAULT_ALLOWED_COMMANDS = ("cat", "grep", "head", "ls", "pwd", "tail", "wc")
SAFE_ENV: Final = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
NETWORK_COMMANDS = ("curl", "ftp", "nc", "ncat", "netcat", "ping", "ssh", "telnet", "wget")
DESTRUCTIVE_COMMANDS = (
    "bash",
    "chmod",
    "chown",
    "cp",
    "fish",
    "mv",
    "rm",
    "sh",
    "sudo",
    "zsh",
)


@dataclass(frozen=True)
class PathDecision:
    decision: Literal["allowed", "blocked"]
    path: Path | None
    reason: str | None = None


@dataclass(frozen=True)
class CommandDecision:
    decision: Literal["allowed", "blocked"]
    argv: tuple[str, ...]
    reason: str | None = None


@dataclass(frozen=True)
class SandboxPolicy:
    allowed_commands: tuple[str, ...] = DEFAULT_ALLOWED_COMMANDS
    timeout_seconds: float = 2.0

    def resolve_path(self, root: Path, raw_path: str) -> PathDecision:
        candidate = Path(raw_path)
        base = root.resolve()
        resolved = (base / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        if not _is_inside(resolved, base):
            return PathDecision(decision="blocked", path=None, reason="path_outside_sandbox")
        return PathDecision(decision="allowed", path=resolved)

    def decide_command(self, raw_command: str | Sequence[str], root: Path) -> CommandDecision:
        argv = _parse_command(raw_command)
        if not argv:
            return CommandDecision(decision="blocked", argv=(), reason="malformed_command")
        command = argv[0]
        if command in NETWORK_COMMANDS or _contains_network_token(argv):
            return CommandDecision(decision="blocked", argv=argv, reason="network_command_blocked")
        if command in DESTRUCTIVE_COMMANDS:
            return CommandDecision(decision="blocked", argv=argv, reason="destructive_command_blocked")
        if command not in self.allowed_commands:
            return CommandDecision(decision="blocked", argv=argv, reason="command_not_allowlisted")
        outside_reason = _outside_path_reason(command, argv, root.resolve())
        if outside_reason is not None:
            return CommandDecision(decision="blocked", argv=argv, reason=outside_reason)
        return CommandDecision(decision="allowed", argv=argv)

    def run_command(self, raw_command: str | Sequence[str], root: Path) -> dict[str, object]:
        decision = self.decide_command(raw_command, root)
        if decision.decision == "blocked":
            return _blocked_command_result(decision.reason or "blocked_by_policy")
        try:
            completed = subprocess.run(
                list(decision.argv),
                cwd=root.resolve(),
                capture_output=True,
                input="",
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
                env=SAFE_ENV,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return _blocked_command_result("command_timeout", handler_executed=True)
        except FileNotFoundError:
            return _blocked_command_result("command_not_found")
        return {
            "decision": "allowed",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "return_code": completed.returncode,
            "handler_executed": True,
            "safe_env": True,
        }


def _parse_command(raw_command: str | Sequence[str]) -> tuple[str, ...]:
    if isinstance(raw_command, str):
        try:
            return tuple(shlex.split(raw_command))
        except ValueError:
            return ()
    result = []
    for item in raw_command:
        if not isinstance(item, str) or not item.strip():
            return ()
        result.append(item)
    return tuple(result)


def _contains_network_token(argv: Sequence[str]) -> bool:
    return any("://" in token or token.startswith("www.") for token in argv)


def _outside_path_reason(command: str, argv: Sequence[str], root: Path) -> str | None:
    for raw_path in _path_arguments(command, argv):
        candidate = Path(raw_path)
        resolved = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        if not _is_inside(resolved, root):
            return "path_outside_sandbox"
    return None


def _path_arguments(command: str, argv: Sequence[str]) -> tuple[str, ...]:
    if command == "pwd":
        return ()
    if command == "grep":
        values = [value for value in argv[1:] if not value.startswith("-")]
        return tuple(values[1:])
    if command in {"cat", "head", "ls", "tail", "wc"}:
        return tuple(value for value in argv[1:] if not value.startswith("-"))
    return ()


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _blocked_command_result(reason: str, handler_executed: bool = False) -> dict[str, object]:
    return {
        "decision": "blocked",
        "reason": reason,
        "stdout": "",
        "stderr": "",
        "return_code": None,
        "handler_executed": handler_executed,
        "safe_env": True,
    }
