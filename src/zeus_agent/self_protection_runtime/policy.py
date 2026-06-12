from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Iterable

from pydantic import JsonValue

from zeus_agent.capability_registry_runtime import SideEffectClass

_HOST_CONFIG_MARKERS: Final[tuple[str, ...]] = (
    "/.claude/settings.json",
    "/.claude/settings.local.json",
    "/.hermes/",
    "/.openclaw/",
)
_COMMAND_KEYS: Final[tuple[str, ...]] = ("command", "cmd", "shell", "input")
_PATH_KEYS: Final[tuple[str, ...]] = (
    "path",
    "file_path",
    "target_path",
    "output_path",
    "destination",
)


@dataclass(frozen=True, slots=True)
class SelfProtectionPolicy:
    roots: tuple[Path, ...] = ()

    def reason_for(
        self,
        *,
        capability_id: str,
        side_effect: SideEffectClass,
        args: dict[str, JsonValue],
    ) -> str | None:
        if not _can_modify(capability_id=capability_id, side_effect=side_effect):
            return None
        if _touches_protected_path(args, roots=self.roots):
            return "self_protection_boundary"
        return None


def _can_modify(*, capability_id: str, side_effect: SideEffectClass) -> bool:
    if side_effect is not SideEffectClass.none:
        return True
    return capability_id.startswith("terminal.run.")


def _touches_protected_path(args: dict[str, JsonValue], *, roots: tuple[Path, ...]) -> bool:
    normalized_roots = tuple(_normalize_path(root) for root in roots)
    for candidate in _candidate_texts(args):
        text = candidate.strip()
        if not text:
            continue
        if _matches_static_marker(text):
            return True
        normalized = _normalize_path(Path(text))
        if any(_inside_or_equal(normalized, root) for root in normalized_roots):
            return True
        if any(root in text for root in normalized_roots):
            return True
    return False


def _candidate_texts(args: dict[str, JsonValue]) -> Iterable[str]:
    for key in _PATH_KEYS:
        value = args.get(key)
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    yield item
    for key in _COMMAND_KEYS:
        value = args.get(key)
        if isinstance(value, str):
            yield value


def _matches_static_marker(text: str) -> bool:
    normalized = text.replace("\\", "/")
    return any(marker in normalized for marker in _HOST_CONFIG_MARKERS)


def _inside_or_equal(candidate: str, root: str) -> bool:
    return candidate == root or candidate.startswith(root.rstrip("/") + "/")


def _normalize_path(path: Path) -> str:
    try:
        return path.expanduser().resolve(strict=False).as_posix()
    except OSError:
        return path.expanduser().absolute().as_posix()
