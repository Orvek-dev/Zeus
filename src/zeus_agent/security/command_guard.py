"""Command risk classifier used before sandbox execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex


HARDLINE_BLOCK_TOKENS = {
    ":(){:|:&};:",
    "mkfs",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
}

DESTRUCTIVE_EXECUTABLES = {
    "rm",
    "rmdir",
    "sudo",
    "chmod",
    "chown",
    "kill",
    "pkill",
    "launchctl",
    "dd",
}

NETWORK_EXECUTABLES = {
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

NETWORK_GIT_SUBCOMMANDS = {"push", "fetch", "pull", "clone"}


@dataclass(frozen=True)
class CommandRisk:
    argv: list[str]
    executable: str
    risk_level: str
    blocked: bool
    reason: str
    needs_checkpoint: bool
    needs_network: bool
    needs_human_approval: bool


def classify_command(argv: list[str], *, network_policy: str = "deny_by_default") -> CommandRisk:
    if not argv:
        return CommandRisk(argv, "", "high", True, "command argv must not be empty", True, False, True)
    executable = Path(argv[0]).name
    lowered = [part.lower() for part in argv]
    command_text = shlex.join(argv).lower()

    if any(token in command_text for token in HARDLINE_BLOCK_TOKENS):
        return _blocked(argv, executable, "hardline dangerous command pattern")
    if executable == "rm" and any(arg in {"-rf", "-fr"} for arg in lowered):
        if any(arg in {"/", "~", "$home", "${home}"} for arg in lowered):
            return _blocked(argv, executable, "root or home recursive deletion is blocked")
        return _risky(argv, executable, "high", "recursive deletion requires a stronger runtime")
    if executable == "dd" and any(arg.startswith(("of=/dev/", "if=/dev/")) for arg in lowered):
        return _blocked(argv, executable, "block device dd is blocked")
    if executable in {"sudo", "launchctl"}:
        return _blocked(argv, executable, f"{executable} is outside Zeus local sandbox policy")

    needs_network = executable in NETWORK_EXECUTABLES or any(
        part.startswith(("http://", "https://", "git@")) for part in lowered
    )
    if len(lowered) >= 2 and executable == "git" and lowered[1] in NETWORK_GIT_SUBCOMMANDS:
        needs_network = True
    if network_policy == "deny_by_default" and needs_network:
        return CommandRisk(
            argv=argv,
            executable=executable,
            risk_level="high",
            blocked=True,
            reason="network access is blocked by deny-by-default policy",
            needs_checkpoint=True,
            needs_network=True,
            needs_human_approval=True,
        )

    if executable in DESTRUCTIVE_EXECUTABLES:
        return _risky(argv, executable, "high", f"{executable} requires explicit high-risk approval")
    if executable == "git" and len(lowered) >= 2 and lowered[1] in {"commit", "merge", "rebase", "reset"}:
        return _risky(argv, executable, "medium", f"git {lowered[1]} requires checkpoint evidence")
    if _looks_like_file_write(lowered):
        return _risky(argv, executable, "medium", "command appears to write files")

    return CommandRisk(
        argv=argv,
        executable=executable,
        risk_level="low",
        blocked=False,
        reason="command accepted by local sandbox policy",
        needs_checkpoint=False,
        needs_network=needs_network,
        needs_human_approval=False,
    )


def _blocked(argv: list[str], executable: str, reason: str) -> CommandRisk:
    return CommandRisk(argv, executable, "high", True, reason, True, False, True)


def _risky(argv: list[str], executable: str, risk_level: str, reason: str) -> CommandRisk:
    return CommandRisk(argv, executable, risk_level, True, reason, True, False, True)


def _looks_like_file_write(lowered: list[str]) -> bool:
    write_flags = {"-w", "--write", "--output", "-o", "--out", "--outfile"}
    if any(part in write_flags for part in lowered):
        return True
    return any(part in {">", ">>"} for part in lowered)

