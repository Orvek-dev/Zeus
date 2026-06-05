from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from pydantic import JsonValue

from zeus_agent.live_research_workflow_execution_registry_runtime.models import (
    LiveResearchWorkflowExecutionRegistryResult,
    ResearchWorkflowExecutionRegistryDecision,
)
from zeus_agent.live_research_workflow_execution_status_runtime import (
    LiveResearchWorkflowExecutionStatusResult,
)


class LiveResearchWorkflowExecutionRegistryRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def record(
        self,
        *,
        status: LiveResearchWorkflowExecutionStatusResult,
        record_ref: str,
    ) -> LiveResearchWorkflowExecutionRegistryResult:
        safe_ref = record_ref.strip()
        path = _records_path(self.home)
        reasons = _record_reasons(status, safe_ref)
        if reasons:
            return _result(decision="blocked", path=path, record_ref=safe_ref, status=status, blocked_reasons=reasons)
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

    def list(self) -> LiveResearchWorkflowExecutionRegistryResult:
        path = _records_path(self.home)
        records = tuple(_read_records(path))
        return _result(decision="listed", path=path, record_count=len(records), records=records)

    def delete(
        self,
        *,
        record_id: str,
        deletion_ref: str,
    ) -> LiveResearchWorkflowExecutionRegistryResult:
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


def _record_reasons(
    status: LiveResearchWorkflowExecutionStatusResult,
    record_ref: str,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if record_ref == "":
        reasons.append("record_ref_required")
    if status.decision != "execution_recorded":
        reasons.append("status_not_recorded")
    if not status.evidence_bound:
        reasons.append("status_evidence_not_bound")
    if not status.no_secret_echo:
        reasons.append("status_secret_echo_detected")
    if status.raw_secret_returned or status.credential_material_accessed:
        reasons.append("status_secret_leak_detected")
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


def _record_payload(
    status: LiveResearchWorkflowExecutionStatusResult,
    record_ref: str,
) -> dict[str, JsonValue]:
    return {
        "record_id": _record_id(status, record_ref),
        "record_ref": record_ref,
        "status_id": status.status_id,
        "workflow_execution_id": status.workflow_execution_id,
        "execution_kind": status.execution_kind,
        "external_network_seen": status.external_network_seen,
        "loopback_network_seen": status.loopback_network_seen,
        "decision": status.decision,
        "production_ready": False,
        "live_production_claimed": False,
        "status": status.to_payload(),
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


def _record_id(status: LiveResearchWorkflowExecutionStatusResult, record_ref: str) -> str:
    payload = {"record_ref": record_ref, "status_id": status.status_id}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-execution-record-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _records_path(home: Path) -> Path:
    return home / "live" / "research-workflow-execution-records.jsonl"


def _result(
    *,
    decision: ResearchWorkflowExecutionRegistryDecision,
    path: Path,
    record_ref: Optional[str] = None,
    status: Optional[LiveResearchWorkflowExecutionStatusResult] = None,
    record_id: Optional[str] = None,
    record_count: int = 0,
    deleted_count: int = 0,
    records: tuple[dict[str, JsonValue], ...] = (),
    blocked_reasons: tuple[str, ...] = (),
) -> LiveResearchWorkflowExecutionRegistryResult:
    return LiveResearchWorkflowExecutionRegistryResult(
        decision=decision,
        record_id=record_id,
        record_ref=record_ref,
        record_path=str(path),
        status_id=None if status is None else status.status_id,
        workflow_execution_id=None if status is None else status.workflow_execution_id,
        execution_kind=None if status is None else status.execution_kind,
        record_count=record_count,
        loopback_execution_record_count=_record_kind_count(records, "loopback"),
        external_execution_record_count=_record_kind_count(records, "external"),
        deleted_count=deleted_count,
        records=records,
        blocked_reasons=blocked_reasons,
        external_network_seen=_external_network_seen(records),
        raw_secret_returned=False if status is None else status.raw_secret_returned,
        no_secret_echo=True if status is None else status.no_secret_echo,
    )


def _record_kind_count(records: tuple[dict[str, JsonValue], ...], kind: str) -> int:
    return sum(1 for record in records if record.get("execution_kind") == kind)


def _external_network_seen(records: tuple[dict[str, JsonValue], ...]) -> bool:
    return any(bool(record.get("external_network_seen")) for record in records)
