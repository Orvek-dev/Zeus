from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Sequence

from zeus_agent.command_parsing import grep_file_operands, is_recursive_grep, parse_command
from zeus_agent.security.credentials import redact_secret_spans

DEFAULT_ALLOWED_COMMANDS = ("cat", "grep", "head", "ls", "pwd", "tail", "wc")
SAFE_ENV: Final = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
NETWORK_COMMANDS = ("curl", "ftp", "nc", "ncat", "netcat", "ping", "ssh", "telnet", "wget")
CREDENTIAL_PATH_NAMES = (
    ".aws",
    ".azure",
    ".docker",
    ".env",
    ".gcp",
    ".kube",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "id_ed25519",
    "id_rsa",
)
CREDENTIAL_MARKERS = ("credential", "private", "secret", "token")
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
        argv = parse_command(raw_command)
        if not argv:
            return CommandDecision(decision="blocked", argv=(), reason="malformed_command")
        command = argv[0]
        if command in NETWORK_COMMANDS or _contains_network_token(argv):
            return CommandDecision(decision="blocked", argv=argv, reason="network_command_blocked")
        if command in DESTRUCTIVE_COMMANDS:
            return CommandDecision(decision="blocked", argv=argv, reason="destructive_command_blocked")
        if command not in self.allowed_commands:
            return CommandDecision(decision="blocked", argv=argv, reason="command_not_allowlisted")
        if command == "grep" and is_recursive_grep(argv):
            return CommandDecision(decision="blocked", argv=argv, reason="recursive_grep_blocked")
        if _is_unbounded_command(argv):
            return CommandDecision(decision="blocked", argv=argv, reason="timeout_or_unbounded_execution")
        outside_reason = _outside_path_reason(command, argv, root.resolve())
        if outside_reason is not None:
            return CommandDecision(decision="blocked", argv=argv, reason=outside_reason)
        credential_reason = _credential_path_reason(command, argv, root.resolve())
        if credential_reason is not None:
            return CommandDecision(decision="blocked", argv=argv, reason=credential_reason)
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
            "stdout": _redact_text(completed.stdout),
            "stderr": _redact_text(completed.stderr),
            "return_code": completed.returncode,
            "handler_executed": True,
            "safe_env": True,
        }

    def protects_credential_path(self, root: Path, path: Path) -> bool:
        return _is_credential_path(path, root.resolve())


def _contains_network_token(argv: Sequence[str]) -> bool:
    return any("://" in token or token.startswith("www.") for token in argv)


def _outside_path_reason(command: str, argv: Sequence[str], root: Path) -> str | None:
    for raw_path in _path_arguments(command, argv):
        candidate = Path(raw_path)
        resolved = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        if not _is_inside(resolved, root):
            return "path_outside_sandbox"
    return None


def _credential_path_reason(command: str, argv: Sequence[str], root: Path) -> str | None:
    for raw_path in _path_arguments(command, argv):
        candidate = Path(raw_path)
        resolved = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        if _is_credential_path(resolved, root):
            return "credential_path"
        if command == "grep" and is_recursive_grep(argv) and _contains_credential_path(resolved, root):
            return "credential_path"
    return None


def _path_arguments(command: str, argv: Sequence[str]) -> tuple[str, ...]:
    if command == "pwd":
        return ()
    if command == "grep":
        return grep_file_operands(argv)
    if command in {"cat", "head", "ls", "tail", "wc"}:
        return tuple(value for value in argv[1:] if not value.startswith("-"))
    return ()


def _is_unbounded_command(argv: Sequence[str]) -> bool:
    return tuple(argv[:2]) in {("tail", "-f"), ("tail", "--follow")}


def _contains_credential_path(path: Path, root: Path) -> bool:
    if not path.is_dir() or not _is_inside(path, root):
        return False
    return any(_is_credential_path(candidate, root) for candidate in path.rglob("*"))


def _is_credential_path(path: Path, root: Path) -> bool:
    try:
        scoped = path.relative_to(root)
    except ValueError:
        scoped = path
    parts = {part.lower() for part in scoped.parts}
    return bool(parts.intersection(CREDENTIAL_PATH_NAMES)) or any(
        marker in part for part in parts for marker in CREDENTIAL_MARKERS
    )


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


def _redact_text(value: str) -> str:
    leading = value[: len(value) - len(value.lstrip())]
    trailing = value[len(value.rstrip()) :]
    return "{0}{1}{2}".format(leading, redact_secret_spans(value.strip()), trailing)
