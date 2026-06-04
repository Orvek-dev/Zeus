from __future__ import annotations

import shlex
from collections.abc import Sequence

GREP_RECURSIVE_OPTIONS = frozenset(("--dereference-recursive", "--recursive"))
GREP_SHORT_VALUE_FLAGS = frozenset(("A", "B", "C", "D", "d", "m"))
GREP_LONG_VALUE_OPTIONS = frozenset((
    "--after-context",
    "--before-context",
    "--binary-files",
    "--context",
    "--devices",
    "--directories",
    "--exclude",
    "--exclude-dir",
    "--include",
    "--label",
    "--max-count",
))


def parse_command(raw_command: str | Sequence[str]) -> tuple[str, ...]:
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


def is_recursive_grep(argv: Sequence[str]) -> bool:
    options_active = True
    index = 1
    while index < len(argv):
        token = argv[index]
        if options_active and token == "--":
            return False
        if options_active and token == "--directories":
            if index + 1 < len(argv) and argv[index + 1] == "recurse":
                return True
            index = min(index + 2, len(argv))
            continue
        if options_active and token.startswith("--directories="):
            if token.split("=", 1)[1] == "recurse":
                return True
            index += 1
            continue
        if token in GREP_RECURSIVE_OPTIONS:
            return True
        if options_active and token.startswith("--"):
            index += 2 if _long_option_requires_value(token) else 1
            continue
        if options_active and token.startswith("-") and token != "-":
            next_index, recursive = _read_short_recursive_option(argv, index)
            if recursive:
                return True
            index = next_index
            continue
        index += 1
    return False


def grep_file_operands(argv: Sequence[str]) -> tuple[str, ...]:
    paths: list[str] = []
    positional: list[str] = []
    pattern_from_option = False
    options_active = True
    index = 1
    while index < len(argv):
        token = argv[index]
        if options_active and token == "--":
            options_active = False
            index += 1
            continue
        if options_active and token.startswith("--"):
            index, option_pattern = _read_long_grep_option(argv, index, paths)
            pattern_from_option = pattern_from_option or option_pattern
            continue
        if options_active and token.startswith("-") and token != "-":
            index, option_pattern = _read_short_grep_option(argv, index, paths)
            pattern_from_option = pattern_from_option or option_pattern
            continue
        positional.append(token)
        index += 1
    if pattern_from_option:
        paths.extend(positional)
    elif positional:
        paths.extend(positional[1:])
    return tuple(path for path in paths if path and path != "-")


def _read_long_grep_option(
    argv: Sequence[str],
    index: int,
    paths: list[str],
) -> tuple[int, bool]:
    token = argv[index]
    if token.startswith("--file="):
        paths.append(token.split("=", 1)[1])
        return index + 1, True
    if token == "--file":
        if index + 1 < len(argv):
            paths.append(argv[index + 1])
            return index + 2, True
        return index + 1, True
    if token.startswith("--regexp="):
        return index + 1, True
    if token == "--regexp":
        return min(index + 2, len(argv)), True
    if _long_option_requires_value(token) and index + 1 < len(argv):
        return index + 2, False
    return index + 1, False


def _read_short_grep_option(
    argv: Sequence[str],
    index: int,
    paths: list[str],
) -> tuple[int, bool]:
    flags = argv[index][1:]
    for position, flag in enumerate(flags):
        suffix = flags[position + 1 :]
        if flag == "f":
            if suffix:
                paths.append(suffix)
                return index + 1, True
            if index + 1 < len(argv):
                paths.append(argv[index + 1])
                return index + 2, True
            return index + 1, True
        if flag == "e":
            return (index + 1 if suffix else min(index + 2, len(argv))), True
        if flag in GREP_SHORT_VALUE_FLAGS:
            return (index + 1 if suffix else min(index + 2, len(argv))), False
    return index + 1, False


def _read_short_recursive_option(argv: Sequence[str], index: int) -> tuple[int, bool]:
    flags = argv[index][1:]
    for position, flag in enumerate(flags):
        suffix = flags[position + 1 :]
        if flag in {"r", "R"}:
            return index + 1, True
        if flag == "d":
            if suffix:
                return index + 1, suffix == "recurse"
            if index + 1 < len(argv):
                return index + 2, argv[index + 1] == "recurse"
            return index + 1, False
        if flag in {"e", "f"} | GREP_SHORT_VALUE_FLAGS:
            return (index + 1 if suffix else min(index + 2, len(argv))), False
    return index + 1, False


def _long_option_requires_value(token: str) -> bool:
    option = token.split("=", 1)[0]
    return option in GREP_LONG_VALUE_OPTIONS and "=" not in token
