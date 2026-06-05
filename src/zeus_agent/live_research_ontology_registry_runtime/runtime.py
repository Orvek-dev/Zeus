from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from zeus_agent.live_research_ontology_ingestion_runtime import LiveResearchOntologyIngestionResult

LiveResearchOntologyRegistryDecision = Literal["recorded", "blocked", "listed", "deleted"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveResearchOntologyRegistryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveResearchOntologyRegistryDecision
    record_id: Optional[str] = None
    record_ref: Optional[str] = None
    record_path: str
    candidate_id: Optional[str] = None
    candidate_ref: Optional[str] = None
    candidate_storage_mode: Literal["local_review_only"] = "local_review_only"
    record_count: int = 0
    deleted_count: int = 0
    records: tuple[dict[str, JsonValue], ...] = Field(default_factory=tuple)
    blocked_reasons: tuple[str, ...] = ()
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveResearchOntologyRegistryRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def record(
        self,
        *,
        ingestion: LiveResearchOntologyIngestionResult,
        record_ref: str,
    ) -> LiveResearchOntologyRegistryResult:
        safe_ref = record_ref.strip()
        path = _records_path(self.home)
        reasons = _record_reasons(ingestion, safe_ref)
        if reasons:
            return _result(
                decision="blocked",
                path=path,
                record_ref=safe_ref,
                ingestion=ingestion,
                blocked_reasons=reasons,
            )
        record = _record_payload(ingestion, safe_ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        return _result(
            decision="recorded",
            path=path,
            record_ref=safe_ref,
            ingestion=ingestion,
            record_id=record["record_id"],
            record_count=len(_read_records(path)),
            records=(record,),
        )

    def list(self) -> LiveResearchOntologyRegistryResult:
        path = _records_path(self.home)
        records = tuple(_read_records(path))
        return _result(
            decision="listed",
            path=path,
            record_count=len(records),
            records=records,
        )

    def delete(self, *, record_id: str, deletion_ref: str) -> LiveResearchOntologyRegistryResult:
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
    ingestion: LiveResearchOntologyIngestionResult,
    record_ref: str,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if record_ref == "":
        reasons.append("record_ref_required")
    if ingestion.decision != "candidate_proposed" or not ingestion.candidate_proposed:
        reasons.append("ontology_candidate_not_proposed")
    if ingestion.candidate_payload is None:
        reasons.append("ontology_candidate_payload_required")
    if ingestion.candidate_status != "proposed_not_promoted" or ingestion.promoted:
        reasons.append("ontology_candidate_promotion_detected")
    if ingestion.ontology_term_promoted or ingestion.active_rule_written or ingestion.authority_widened:
        reasons.append("ontology_candidate_promotion_detected")
    if ingestion.requested_live_transport or ingestion.requested_rule_promotion:
        reasons.append("ontology_candidate_promotion_detected")
    if not ingestion.no_secret_echo or ingestion.credential_material_accessed or ingestion.raw_secret_returned:
        reasons.append("ontology_candidate_secret_leak_detected")
    if ingestion.live_production_claimed:
        reasons.append("ontology_candidate_production_claim_detected")
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
    ingestion: LiveResearchOntologyIngestionResult,
    record_ref: str,
) -> dict[str, JsonValue]:
    record_id = _record_id(ingestion, record_ref)
    return {
        "record_id": record_id,
        "record_ref": record_ref,
        "candidate_id": ingestion.candidate_id,
        "candidate_ref": ingestion.candidate_ref,
        "candidate_status": ingestion.candidate_status,
        "term": ingestion.term,
        "provenance_count": ingestion.provenance_count,
        "candidate_storage_mode": "local_review_only",
        "promoted": False,
        "live_production_claimed": False,
        "candidate": ingestion.candidate_payload,
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


def _record_id(ingestion: LiveResearchOntologyIngestionResult, record_ref: str) -> str:
    payload = {
        "candidate_id": ingestion.candidate_id,
        "candidate_ref": ingestion.candidate_ref,
        "record_ref": record_ref,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-ontology-record-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _records_path(home: Path) -> Path:
    return home / "ontology" / "live-research-candidates.jsonl"


def _result(
    *,
    decision: LiveResearchOntologyRegistryDecision,
    path: Path,
    record_ref: Optional[str] = None,
    ingestion: Optional[LiveResearchOntologyIngestionResult] = None,
    record_id: Optional[str] = None,
    record_count: int = 0,
    deleted_count: int = 0,
    records: tuple[dict[str, JsonValue], ...] = (),
    blocked_reasons: tuple[str, ...] = (),
) -> LiveResearchOntologyRegistryResult:
    return LiveResearchOntologyRegistryResult(
        decision=decision,
        record_id=record_id,
        record_ref=record_ref,
        record_path=str(path),
        candidate_id=None if ingestion is None else ingestion.candidate_id,
        candidate_ref=None if ingestion is None else ingestion.candidate_ref,
        candidate_storage_mode="local_review_only",
        record_count=record_count,
        deleted_count=deleted_count,
        records=records,
        blocked_reasons=blocked_reasons,
        network_opened=False,
        handler_executed=False,
        credential_material_accessed=False,
        raw_secret_returned=False if ingestion is None else ingestion.raw_secret_returned,
        no_secret_echo=True if ingestion is None else ingestion.no_secret_echo,
        live_production_claimed=False,
    )
