from __future__ import annotations

import re
import shlex
from typing import Final

from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.trust_loop_runtime import ActionRisk, Reversibility

from .models import CommandRisk, make_risk

_READ_ONLY: Final = frozenset(
    {
        "cat",
        "ls",
        "pwd",
        "head",
        "tail",
        "wc",
        "grep",
        "echo",
        "stat",
        "file",
        "which",
        "env",
        "date",
        "printf",
        "true",
        "false",
        ":",
    }
)
_LOCAL_WRITE: Final = frozenset({"mv", "cp", "touch", "mkdir", "ln", "tee"})
_DESTRUCTIVE: Final = frozenset({"rm", "dd", "mkfs", "shred", "truncate", "shutdown", "reboot", "kill", "killall"})
_NETWORK: Final = frozenset({"curl", "wget", "ssh", "scp", "nc", "ncat", "ftp", "rsync", "ping"})
_PACKAGE: Final = frozenset({"apt", "apt-get", "yum", "dnf", "brew", "pip", "pip3", "npm", "pnpm", "yarn", "gem", "cargo"})
_PROBE_PROGRAMS: Final = frozenset(
    {
        "python",
        "python3",
        "pytest",
        "ruff",
        "zeus",
        "hermes",
        "git",
        "pip",
        "pip3",
        "node",
        "npm",
    }
)
_PROBE_ARGS: Final = frozenset({"--version", "-V", "--help", "-h"})
_PYTEST_PROBE_ARGS: Final = frozenset({"--collect-only", "--version", "--help", "-h", "-q", "--quiet"})
_PYTEST_REQUIRED_PROBES: Final = frozenset({"--collect-only", "--version", "--help", "-h"})
_PIP_READ_ONLY_SUBCOMMANDS: Final = frozenset({"check", "freeze", "list", "show"})
_PIP_READ_ONLY_FLAGS: Final = frozenset(
    {"--files", "-f", "--format", "--local", "--not-required", "--path", "--verbose", "-v"}
)
_GIT_READ_ONLY: Final = frozenset(
    {"status", "log", "diff", "show", "branch", "rev-parse", "describe", "ls-files", "grep"}
)
_GIT_NETWORK: Final = frozenset({"push", "pull", "fetch", "clone", "ls-remote"})
_FIND_WRITE_FLAGS: Final = frozenset({"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fls", "-fprint", "-fprintf"})
_SAFE_ZEUS_MODULE_PROBES: Final = frozenset({"zeus_agent", "zeus_agent.cli_main", "src.zeus_agent"})
_PYTHON_VERSIONED_RE: Final = re.compile(r"python3(?:\.\d+)?")
_REDIRECT_RE: Final = re.compile(r"\d*&?>>?\s*(?P<target>&?\S+)")
_DISCARD_TARGETS: Final = frozenset({"/dev/null", "/dev/stdout", "/dev/stderr"})


def classify_segment(text: str) -> CommandRisk:
    try:
        tokens = shlex.split(text)
    except ValueError:
        return make_risk(
            "?",
            SideEffectClass.account_write,
            Reversibility.irreversible,
            ActionRisk.high,
            ("unparseable_command",),
        )
    if not tokens:
        return make_risk("", SideEffectClass.none, Reversibility.reversible, ActionRisk.low, ("empty_command",))
    program = tokens[0]
    reasons: list[str] = []

    has_redirect = _has_file_write_redirect(text)
    rf = program == "rm" and any(arg in {"-rf", "-fr", "-r", "-R"} for arg in tokens[1:])

    if _is_read_only_probe(program, tokens[1:]):
        reasons.append("read_only_probe")
        return make_risk(program, SideEffectClass.none, Reversibility.reversible, ActionRisk.low, tuple(reasons))
    if _is_read_only_python_module_probe(program, tokens[1:]):
        reasons.append("python_module_probe")
        return make_risk(program, SideEffectClass.none, Reversibility.reversible, ActionRisk.low, tuple(reasons))
    if _is_read_only_pytest_probe(program, tokens[1:]):
        reasons.append("pytest_probe")
        return make_risk(program, SideEffectClass.none, Reversibility.reversible, ActionRisk.low, tuple(reasons))
    if _is_read_only_command_probe(program, tokens[1:]):
        reasons.append("command_probe")
        return make_risk(program, SideEffectClass.none, Reversibility.reversible, ActionRisk.low, tuple(reasons))
    if program == "git":
        return _classify_git(tokens)
    if program in _DESTRUCTIVE or rf:
        reasons.append("destructive_command")
        return make_risk(program, SideEffectClass.account_write, Reversibility.irreversible, ActionRisk.high, tuple(reasons))
    if program in _NETWORK:
        reasons.append("network_command")
        return make_risk(program, SideEffectClass.account_write, Reversibility.irreversible, ActionRisk.high, tuple(reasons))
    if program in _PACKAGE:
        reasons.append("package_mutation")
        return make_risk(program, SideEffectClass.account_write, Reversibility.compensable, ActionRisk.medium, tuple(reasons))
    if program == "find":
        return _classify_find(tokens, has_redirect)
    if program == "sed":
        return _classify_sed(tokens, has_redirect)
    if program == "sort":
        return _classify_sort(tokens, has_redirect)
    if program in _LOCAL_WRITE or has_redirect:
        if has_redirect:
            reasons.append("output_redirect")
        else:
            reasons.append("local_mutation")
        return make_risk(program, SideEffectClass.local_write, Reversibility.compensable, ActionRisk.medium, tuple(reasons))
    if program in _READ_ONLY:
        reasons.append("read_only")
        return make_risk(program, SideEffectClass.none, Reversibility.reversible, ActionRisk.low, tuple(reasons))
    reasons.append("unknown_program")
    return make_risk(program, SideEffectClass.account_write, Reversibility.irreversible, ActionRisk.high, tuple(reasons))


def _has_file_write_redirect(text: str) -> bool:
    for match in _REDIRECT_RE.finditer(text):
        target = match.group("target")
        if target.startswith("&"):
            continue
        if target in _DISCARD_TARGETS:
            continue
        return True
    return False


def _is_read_only_probe(program: str, args: list[str]) -> bool:
    if _probe_program_name(program) not in _PROBE_PROGRAMS:
        return False
    return bool(args) and all(arg in _PROBE_ARGS for arg in args)


def _is_read_only_python_module_probe(program: str, args: list[str]) -> bool:
    if _probe_program_name(program) not in {"python", "python3"} or len(args) < 2 or args[0] != "-m":
        return False
    if args[1] == "pytest":
        return _is_pytest_probe_args(args[2:])
    if args[1] == "pip":
        return _is_read_only_pip_module_probe(args[2:])
    if args[1] in _SAFE_ZEUS_MODULE_PROBES:
        return bool(args[2:]) and all(arg in _PROBE_ARGS for arg in args[2:])
    return False


def _is_read_only_pytest_probe(program: str, args: list[str]) -> bool:
    return _probe_program_name(program) == "pytest" and _is_pytest_probe_args(args)


def _probe_program_name(program: str) -> str:
    name = program.rsplit("/", 1)[-1]
    if _PYTHON_VERSIONED_RE.fullmatch(name):
        return "python3"
    return name


def _is_pytest_probe_args(args: list[str]) -> bool:
    return (
        bool(args)
        and all(arg in _PYTEST_PROBE_ARGS for arg in args)
        and any(arg in _PYTEST_REQUIRED_PROBES for arg in args)
    )


def _is_read_only_pip_module_probe(args: list[str]) -> bool:
    if not args:
        return False
    if all(arg in _PROBE_ARGS for arg in args):
        return True
    return args[0] in _PIP_READ_ONLY_SUBCOMMANDS and all(_pip_arg_is_read_only(arg) for arg in args[1:])


def _pip_arg_is_read_only(arg: str) -> bool:
    return not arg.startswith("-") or arg in _PIP_READ_ONLY_FLAGS


def _is_read_only_command_probe(program: str, args: list[str]) -> bool:
    return program == "command" and len(args) == 2 and args[0] in {"-v", "-V"} and bool(args[1])


def _classify_git(tokens: list[str]) -> CommandRisk:
    subcommand = _git_subcommand(tokens)
    if subcommand is None:
        return make_risk(
            "git",
            SideEffectClass.account_write,
            Reversibility.irreversible,
            ActionRisk.high,
            ("git_unknown_subcommand",),
        )
    if subcommand == "remote":
        if _git_remote_is_read_only(tokens):
            return make_risk(
                "git",
                SideEffectClass.none,
                Reversibility.reversible,
                ActionRisk.low,
                ("git_remote_read_only",),
            )
        return make_risk(
            "git",
            SideEffectClass.local_write,
            Reversibility.compensable,
            ActionRisk.medium,
            ("git_remote_mutation",),
        )
    if subcommand in _GIT_READ_ONLY:
        return make_risk(
            "git",
            SideEffectClass.none,
            Reversibility.reversible,
            ActionRisk.low,
            ("git_read_only",),
        )
    if subcommand in _GIT_NETWORK:
        return make_risk(
            "git",
            SideEffectClass.account_write,
            Reversibility.irreversible,
            ActionRisk.high,
            ("git_network_command",),
        )
    return make_risk("git", SideEffectClass.local_write, Reversibility.compensable, ActionRisk.medium, ("git_mutation",))


def _git_remote_is_read_only(tokens: list[str]) -> bool:
    after_remote = tokens[tokens.index("remote") + 1 :]
    return all(token in {"-v", "--verbose"} for token in after_remote)


def _classify_find(tokens: list[str], has_redirect: bool) -> CommandRisk:
    if any(token in _FIND_WRITE_FLAGS for token in tokens[1:]):
        return make_risk("find", SideEffectClass.account_write, Reversibility.irreversible, ActionRisk.high, ("find_action",))
    if has_redirect:
        return make_risk("find", SideEffectClass.local_write, Reversibility.compensable, ActionRisk.medium, ("output_redirect",))
    return make_risk("find", SideEffectClass.none, Reversibility.reversible, ActionRisk.low, ("find_read_only",))


def _classify_sed(tokens: list[str], has_redirect: bool) -> CommandRisk:
    if any(token == "-i" or token.startswith("-i") for token in tokens[1:]):
        return make_risk("sed", SideEffectClass.local_write, Reversibility.compensable, ActionRisk.medium, ("sed_in_place",))
    if has_redirect:
        return make_risk("sed", SideEffectClass.local_write, Reversibility.compensable, ActionRisk.medium, ("output_redirect",))
    return make_risk("sed", SideEffectClass.none, Reversibility.reversible, ActionRisk.low, ("sed_read_only",))


def _classify_sort(tokens: list[str], has_redirect: bool) -> CommandRisk:
    if "-o" in tokens[1:] or any(token.startswith("--output") for token in tokens[1:]):
        return make_risk("sort", SideEffectClass.local_write, Reversibility.compensable, ActionRisk.medium, ("sort_output",))
    if has_redirect:
        return make_risk("sort", SideEffectClass.local_write, Reversibility.compensable, ActionRisk.medium, ("output_redirect",))
    return make_risk("sort", SideEffectClass.none, Reversibility.reversible, ActionRisk.low, ("sort_read_only",))


def _git_subcommand(tokens: list[str]) -> str | None:
    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        return token
    return None
