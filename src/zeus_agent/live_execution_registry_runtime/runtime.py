from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from zeus_agent.live_execution_status_runtime import LiveExecutionStatusResult

LiveExecutionRegistryDecision = Literal["recorded", "blocked", "listed", "deleted"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveExecutionRegistryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveExecutionRegistryDecision
    record_id: Optional[str] = None
    record_ref: Optional[str] = None
    record_path: str
    status_id: Optional[str] = None
    record_count: int = 0
    deleted_count: int = 0
    records: tuple[dict[str, JsonValue], ...] = Field(default_factory=tuple)
    blocked_reasons: tuple[str, ...] = ()
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveExecutionRegistryRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def record(self, *, status: LiveExecutionStatusResult, record_ref: str) -> LiveExecutionRegistryResult:
        safe_ref = record_ref.strip()
        path = _records_path(self.home)
        reasons = _record_reasons(status, safe_ref)
        if reasons:
            return _result(
                decision="blocked",
                path=path,
                record_ref=safe_ref,
                status=status,
                blocked_reasons=reasons,
            )
        record = _record_payload(status, safe_ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        return _result(
            decision="recorded",
            path=path,
            record_ref=safe_ref,
            status=status,
            record_id=record["record_id"],
            record_count=len(_read_records(path)),
            records=(record,),
        )

    def list(self) -> LiveExecutionRegistryResult:
        path = _records_path(self.home)
        records = tuple(_read_records(path))
        return _result(
            decision="listed",
            path=path,
            record_count=len(records),
            records=records,
        )

    def delete(self, *, record_id: str, deletion_ref: str) -> LiveExecutionRegistryResult:
        safe_record_id = record_id.strip()
        safe_deletion_ref = deletion_ref.strip()
        path = _records_path(self.home)
        records = _read_records(path)
        reasons = _delete_reasons(safe_record_id, safe_deletion_ref, records)
        if reasons:
            return _result(
                decision="blocked",
                path=path,
                record_id=safe_record_id or None,
                record_ref=safe_deletion_ref,
                record_count=len(records),
                records=tuple(records),
                blocked_reasons=reasons,
            )
        kept = [record for record in records if record.get("record_id") != safe_record_id]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for record in kept:
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        return _result(
            decision="deleted",
            path=path,
            record_id=safe_record_id,
            record_ref=safe_deletion_ref,
            record_count=len(kept),
            records=tuple(kept),
            deleted_count=len(records) - len(kept),
        )


def _record_reasons(status: LiveExecutionStatusResult, record_ref: str) -> tuple[str, ...]:
    reasons: list[str] = []
    if record_ref == "":
        reasons.append("record_ref_required")
    if not status.no_secret_echo:
        reasons.append("status_secret_echo_detected")
    if status.raw_secret_returned:
        reasons.append("status_raw_secret_returned")
    if status.live_production_claimed:
        reasons.append("status_live_production_claimed")
    return tuple(dict.fromkeys(reasons))


def _delete_reasons(
    record_id: str,
    deletion_ref: str,
    records: list[dict[str, JsonValue]],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if record_id == "":
        reasons.append("record_id_required")
    if deletion_ref == "":
        reasons.append("deletion_ref_required")
    if record_id and not any(record.get("record_id") == record_id for record in records):
        reasons.append("record_not_found")
    return tuple(dict.fromkeys(reasons))


def _record_payload(status: LiveExecutionStatusResult, record_ref: str) -> dict[str, JsonValue]:
    payload = status.to_payload()
    record_id = _record_id(status, record_ref)
    return {
        "record_id": record_id,
        "record_ref": record_ref,
        "status_id": status.status_id,
        "decision": status.decision,
        "bundle_id": status.bundle_id,
        "review_id": status.review_id,
        "production_ready": False,
        "live_production_claimed": False,
        "status": payload,
    }


def _read_records(path: Path) -> list[dict[str, JsonValue]]:
    if not path.exists():
        return []
    records: list[dict[str, JsonValue]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            records.append(item)
    return records


def _record_id(status: LiveExecutionStatusResult, record_ref: str) -> str:
    payload = {"record_ref": record_ref, "status_id": status.status_id, "decision": status.decision}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-execution-record-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _records_path(home: Path) -> Path:
    return home / "live" / "execution-records.jsonl"


def _result(
    *,
    decision: LiveExecutionRegistryDecision,
    path: Path,
    record_ref: Optional[str] = None,
    status: Optional[LiveExecutionStatusResult] = None,
    record_id: Optional[str] = None,
    record_count: int = 0,
    deleted_count: int = 0,
    records: tuple[dict[str, JsonValue], ...] = (),
    blocked_reasons: tuple[str, ...] = (),
) -> LiveExecutionRegistryResult:
    return LiveExecutionRegistryResult(
        decision=decision,
        record_id=record_id,
        record_ref=record_ref,
        record_path=str(path),
        status_id=None if status is None else status.status_id,
        record_count=record_count,
        deleted_count=deleted_count,
        records=records,
        blocked_reasons=blocked_reasons,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        raw_secret_returned=False if status is None else status.raw_secret_returned,
        no_secret_echo=True if status is None else status.no_secret_echo,
        live_production_claimed=False,
    )
