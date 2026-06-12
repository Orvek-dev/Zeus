from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from zeus_agent.adapters.claude_code_hook import ControlPlaneState


def default_home() -> Path:
    return Path.home() / ".zeus"


def state_for_home(home: Path | None) -> ControlPlaneState:
    from zeus_agent.adapters.claude_code_hook import ControlPlaneState

    return ControlPlaneState(home if home is not None else default_home())


def echo_json(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def is_loopback(bind: str) -> bool:
    return bind.strip().lower() in {"127.0.0.1", "::1", "localhost", "[::1]"}


def parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
