"""Private JSON persistence helpers."""

from __future__ import annotations

from datetime import date, datetime
import json
import os
from pathlib import Path
from typing import Any

from zeus_agent.paths import PRIVATE_FILE_MODE, ensure_private_dir


def _default(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"object is not JSON serializable: {type(value)!r}")


def write_private_json(path: Path, value: Any) -> Path:
    ensure_private_dir(path.parent)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=_default) + "\n",
        encoding="utf-8",
    )
    os.chmod(tmp_path, PRIVATE_FILE_MODE)
    tmp_path.replace(path)
    try:
        os.chmod(path, PRIVATE_FILE_MODE)
    except PermissionError:
        pass
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def append_private_jsonl(path: Path, value: Any) -> Path:
    ensure_private_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, default=_default) + "\n")
    try:
        os.chmod(path, PRIVATE_FILE_MODE)
    except PermissionError:
        pass
    return path
