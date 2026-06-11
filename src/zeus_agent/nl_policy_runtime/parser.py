from __future__ import annotations

import re
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

_MICROUSD_PER_USD: Final = 1_000_000

_SUPPORTED: Final = (
    'budget: "주(weekly) 예산 $12" / "weekly budget $12"',
    'rate: "분당 호출 20회" / "max 20 calls per minute"',
    'tool budget: "mcp.files.echo 하루 5회" / "mcp.files.echo 5 per day"',
    'quiet hours: "조용 시간 22-07" / "quiet hours 22-07"',
)

_WEEKLY_BUDGET: Final = re.compile(
    r"(?:weekly\s+budget|주(?:간)?\s*예산)\s*\$?\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE
)
_RATE: Final = re.compile(
    r"(?:max\s+([0-9]+)\s+calls?\s+per\s+minute|분당\s*호출\s*([0-9]+)\s*회)", re.IGNORECASE
)
_TOOL_DAILY: Final = re.compile(
    r"([a-z0-9_.\-]+)\s+(?:([0-9]+)\s+per\s+day|하루\s*([0-9]+)\s*회)", re.IGNORECASE
)
_QUIET: Final = re.compile(
    r"(?:quiet\s+hours|조용\s*시간)\s*([0-2]?[0-9])\s*-\s*([0-2]?[0-9])", re.IGNORECASE
)


class RuleDiff(BaseModel):
    """What WOULD change — shown to the human before anything is written."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    kind: str
    preview: str
    settings: dict[str, JsonValue]


def parse_nl_rule(text: str) -> Optional[RuleDiff]:
    cleaned = text.strip()
    match = _WEEKLY_BUDGET.search(cleaned)
    if match:
        usd = float(match.group(1))
        units = int(usd * _MICROUSD_PER_USD)
        return RuleDiff(
            kind="weekly_budget",
            preview="fleet 주간 예산 한도 → ${0:.2f} ({1} units)".format(usd, units),
            settings={"scope": "fleet", "scope_id": "fleet", "limit_units": units},
        )
    match = _RATE.search(cleaned)
    if match:
        calls = int(match.group(1) or match.group(2))
        return RuleDiff(
            kind="rate",
            preview="모든 능력 호출 한도 → 분당 {0}회".format(calls),
            settings={"governor.rate_max_calls": calls, "governor.rate_window_seconds": 60},
        )
    match = _QUIET.search(cleaned)
    if match:
        start, end = int(match.group(1)) % 24, int(match.group(2)) % 24
        value = "{0:02d}-{1:02d}".format(start, end)
        return RuleDiff(
            kind="quiet_hours",
            preview="조용 시간 → {0} (ASK는 아침까지 대기열로)".format(value),
            settings={"policy.quiet_hours": value},
        )
    match = _TOOL_DAILY.search(cleaned)
    if match and "." in match.group(1):
        capability_id = match.group(1)
        calls = int(match.group(2) or match.group(3))
        return RuleDiff(
            kind="tool_budget",
            preview="{0} 호출 한도 → 하루 {1}회".format(capability_id, calls),
            settings={"scope": "capability", "scope_id": capability_id, "limit_units": calls},
        )
    return None


def supported_grammar() -> tuple[str, ...]:
    return _SUPPORTED


def apply_rule_diff(diff: RuleDiff, store: SQLiteControlPlaneStore) -> dict[str, JsonValue]:
    if diff.kind in {"weekly_budget", "tool_budget"}:
        store.set_budget_limit(
            str(diff.settings["scope"]),
            str(diff.settings["scope_id"]),
            int(diff.settings["limit_units"]),
        )
    else:
        for key, value in diff.settings.items():
            store.kv_set(key, str(value))
    return {"applied": True, "kind": diff.kind, "preview": diff.preview}
