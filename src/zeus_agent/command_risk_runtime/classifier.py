from __future__ import annotations

import shlex
from typing import Final

from pydantic import BaseModel, ConfigDict

from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.trust_loop_runtime import ActionRisk, Reversibility

# Read-only programs: no side effect.
_READ_ONLY: Final = frozenset(
    {"cat", "ls", "pwd", "head", "tail", "wc", "grep", "echo", "stat", "file", "which", "env", "date"}
)
# Local mutations that are recoverable (compensable).
_LOCAL_WRITE: Final = frozenset({"mv", "cp", "touch", "mkdir", "ln", "sed", "tee"})
# Irreversible / destructive local programs.
_DESTRUCTIVE: Final = frozenset({"rm", "dd", "mkfs", "shred", "truncate", "shutdown", "reboot", "kill", "killall"})
# Network / account-scope programs.
_NETWORK: Final = frozenset({"curl", "wget", "ssh", "scp", "nc", "ncat", "ftp", "rsync", "git", "ping"})
# Package / environment mutation.
_PACKAGE: Final = frozenset({"apt", "apt-get", "yum", "dnf", "brew", "pip", "pip3", "npm", "pnpm", "yarn", "gem", "cargo"})

_REDIRECT_MARKERS: Final = (">", ">>")


class CommandRisk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    program: str
    side_effect: SideEffectClass
    reversibility: Reversibility
    risk: ActionRisk
    reasons: tuple[str, ...]


def classify_command(command: str) -> CommandRisk:
    """Classify a shell command, fail-closed: anything unrecognized is treated as
    an account-scope, irreversible action requiring approval."""
    text = command.strip()
    if text == "":
        return _risk("", SideEffectClass.none, Reversibility.reversible, ActionRisk.low, ("empty_command",))
    try:
        tokens = shlex.split(text)
    except ValueError:
        return _risk("?", SideEffectClass.account_write, Reversibility.irreversible, ActionRisk.high, ("unparseable_command",))
    program = tokens[0]
    reasons: list[str] = []

    has_redirect = any(marker in text for marker in _REDIRECT_MARKERS)
    has_pipe_to_shell = "| sh" in text or "| bash" in text or "|sh" in text or "|bash" in text
    rf = program == "rm" and any(arg in {"-rf", "-fr", "-r", "-R"} for arg in tokens[1:])

    if has_pipe_to_shell:
        reasons.append("pipe_to_shell")
        return _risk(program, SideEffectClass.account_write, Reversibility.irreversible, ActionRisk.high, tuple(reasons))
    if program in _DESTRUCTIVE or rf:
        reasons.append("destructive_command")
        return _risk(program, SideEffectClass.account_write, Reversibility.irreversible, ActionRisk.high, tuple(reasons))
    if program in _NETWORK:
        reasons.append("network_command")
        return _risk(program, SideEffectClass.account_write, Reversibility.irreversible, ActionRisk.high, tuple(reasons))
    if program in _PACKAGE:
        reasons.append("package_mutation")
        return _risk(program, SideEffectClass.account_write, Reversibility.compensable, ActionRisk.medium, tuple(reasons))
    if program in _LOCAL_WRITE or has_redirect:
        if has_redirect:
            reasons.append("output_redirect")
        else:
            reasons.append("local_mutation")
        return _risk(program, SideEffectClass.local_write, Reversibility.compensable, ActionRisk.medium, tuple(reasons))
    if program in _READ_ONLY:
        reasons.append("read_only")
        return _risk(program, SideEffectClass.none, Reversibility.reversible, ActionRisk.low, tuple(reasons))
    # Unknown program → fail closed.
    reasons.append("unknown_program")
    return _risk(program, SideEffectClass.account_write, Reversibility.irreversible, ActionRisk.high, tuple(reasons))


def _risk(
    program: str,
    side_effect: SideEffectClass,
    reversibility: Reversibility,
    risk: ActionRisk,
    reasons: tuple[str, ...],
) -> CommandRisk:
    return CommandRisk(
        program=program,
        side_effect=side_effect,
        reversibility=reversibility,
        risk=risk,
        reasons=reasons,
    )
