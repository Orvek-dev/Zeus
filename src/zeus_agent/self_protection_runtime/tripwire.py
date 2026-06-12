from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import JsonValue

from zeus_agent.trust_loop_runtime import FlightRecorder, SQLiteControlPlaneStore

_KV_TRIPWIRE_SNAPSHOT: Final = "self_protection.tripwire.snapshot.v1"
_MISSING: Final = "<missing>"


@dataclass(frozen=True, slots=True)
class TripwireChange:
    path: str
    before: str
    after: str

    def to_payload(self) -> dict[str, JsonValue]:
        return {"path": self.path, "before": self.before, "after": self.after}


def snapshot_tripwire(store: SQLiteControlPlaneStore, paths: tuple[Path, ...]) -> int:
    snapshot = _snapshot(paths)
    store.kv_set(_KV_TRIPWIRE_SNAPSHOT, json.dumps(snapshot, sort_keys=True))
    return len(snapshot)


def check_tripwire(
    store: SQLiteControlPlaneStore,
    recorder: FlightRecorder,
    paths: tuple[Path, ...],
) -> tuple[TripwireChange, ...]:
    before = _load_snapshot(store)
    after = _snapshot(paths)
    changes = tuple(
        TripwireChange(path=path, before=before.get(path, _MISSING), after=after[path])
        for path in sorted(after)
        if before.get(path, _MISSING) != after[path]
    )
    if changes:
        recorder.ledger.append(
            kind="tripwire",
            run_id="self_protection.tripwire",
            payload={"changed": [change.to_payload() for change in changes]},
        )
    return changes


def _load_snapshot(store: SQLiteControlPlaneStore) -> dict[str, str]:
    raw = store.kv_get(_KV_TRIPWIRE_SNAPSHOT)
    if raw is None:
        return {}
    try:
        decoded = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(decoded, dict):
        return {}
    return {str(key): str(value) for key, value in decoded.items()}


def _snapshot(paths: tuple[Path, ...]) -> dict[str, str]:
    return {_path_key(path): _file_digest(path) for path in paths}


def _path_key(path: Path) -> str:
    return path.expanduser().resolve(strict=False).as_posix()


def _file_digest(path: Path) -> str:
    if not path.exists():
        return _MISSING
    if path.is_dir():
        return "<dir>"
    return hashlib.sha256(path.read_bytes()).hexdigest()
