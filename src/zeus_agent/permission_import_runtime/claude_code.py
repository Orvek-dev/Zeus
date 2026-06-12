from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import JsonValue

_SAFE_BASH_PREFIXES: Final[tuple[str, ...]] = (
    "git status",
    "git diff",
    "git log",
    "ls",
    "pwd",
    "python --version",
    "python3 --version",
)
_DANGEROUS_MARKERS: Final[tuple[str, ...]] = (
    "rm ",
    "rm -",
    "sudo ",
    "curl ",
    "wget ",
    "git push",
    "chmod ",
    "chown ",
)


@dataclass(frozen=True, slots=True)
class ImportedPermission:
    source_rule: str
    capability_id: str
    tier: str
    provenance: str

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "source_rule": self.source_rule,
            "capability_id": self.capability_id,
            "tier": self.tier,
            "provenance": self.provenance,
        }


def summarize_claude_code_settings(settings_path: Path) -> dict[str, JsonValue]:
    data = _read_json(settings_path)
    allow_rules = _allow_rules(data)
    imported = tuple(_map_rule(rule, settings_path=settings_path) for rule in allow_rules)
    return {
        "host": "claude-code",
        "settings": str(settings_path),
        "secret_material": "excluded",
        "tiers": {
            "low": sum(1 for item in imported if item.tier == "low"),
            "medium": sum(1 for item in imported if item.tier == "medium"),
            "high": sum(1 for item in imported if item.tier == "high"),
        },
        "candidates": [item.to_payload() for item in imported],
        "operator_note": (
            "Zeus imports permission rules only; raw API keys and env secrets stay outside grants."
        ),
    }


def _read_json(path: Path) -> dict[str, JsonValue]:
    decoded = json.loads(path.read_text(encoding="utf-8"))
    return decoded if isinstance(decoded, dict) else {}


def _allow_rules(data: dict[str, JsonValue]) -> tuple[str, ...]:
    permissions = data.get("permissions")
    if not isinstance(permissions, dict):
        return ()
    allow = permissions.get("allow")
    if not isinstance(allow, list):
        return ()
    return tuple(item.strip() for item in allow if isinstance(item, str) and item.strip())


def _map_rule(rule: str, *, settings_path: Path) -> ImportedPermission:
    capability_id = _capability_for_rule(rule)
    return ImportedPermission(
        source_rule=rule,
        capability_id=capability_id,
        tier=_tier_for_rule(rule),
        provenance="imported:{0}".format(settings_path.name),
    )


def _capability_for_rule(rule: str) -> str:
    lowered = rule.lower()
    if lowered.startswith("read("):
        return "fs.read"
    if lowered.startswith("edit(") or lowered.startswith("write("):
        return "fs.write"
    if lowered.startswith("bash("):
        command = _bash_command(rule)
        return "terminal.run.read" if _safe_bash(command) else "terminal.run.external"
    return "host.permission"


def _tier_for_rule(rule: str) -> str:
    lowered = rule.lower()
    if lowered.startswith("read("):
        return "low"
    if lowered.startswith("bash(") and _safe_bash(_bash_command(rule)):
        return "low"
    if any(marker in lowered for marker in _DANGEROUS_MARKERS):
        return "high"
    return "medium"


def _bash_command(rule: str) -> str:
    start = rule.find("(")
    end = rule.rfind(")")
    if start == -1 or end <= start:
        return ""
    return rule[start + 1 : end].split(":", maxsplit=1)[0].strip().lower()


def _safe_bash(command: str) -> bool:
    return any(command == prefix or command.startswith(prefix + " ") for prefix in _SAFE_BASH_PREFIXES)
