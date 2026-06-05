from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.skill_eval_registry_runtime.models import SkillEvalRegistryDecision
from zeus_agent.skill_eval_registry_runtime.models import SkillEvalRegistryResult
from zeus_agent.skill_eval_runtime import SkillEvalResult

_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=sk",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


class SkillEvalRegistryRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def record(self, *, eval_result: SkillEvalResult, eval_ref: str) -> SkillEvalRegistryResult:
        safe_ref = eval_ref.strip()
        path = _records_path(self.home)
        reasons = _record_reasons(eval_result=eval_result, eval_ref=safe_ref)
        if reasons:
            return _result(
                decision="blocked",
                path=path,
                eval_ref=safe_ref,
                eval_result=eval_result,
                blocked_reasons=reasons,
            )
        record = _record_payload(eval_result=eval_result, eval_ref=safe_ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        records = tuple(_read_records(path))
        return _result(
            decision="recorded",
            path=path,
            eval_ref=safe_ref,
            eval_result=eval_result,
            eval_record_id=record["eval_record_id"],
            records=(record,),
            record_count=len(records),
        )

    def list(self) -> SkillEvalRegistryResult:
        path = _records_path(self.home)
        records = tuple(_read_records(path))
        return _result(decision="listed", path=path, records=records, record_count=len(records))


def _record_reasons(*, eval_result: SkillEvalResult, eval_ref: str) -> tuple[str, ...]:
    reasons: list[str] = []
    if eval_ref == "":
        reasons.append("skill_eval_ref_required")
    if eval_result.decision not in {"evaluated", "blocked"}:
        reasons.append("skill_eval_decision_not_recordable")
    if eval_result.promotion_allowed or eval_result.active_skill_written or eval_result.active_rule_written:
        reasons.append("skill_eval_promotion_or_activation_detected")
    if eval_result.authority_widened:
        reasons.append("skill_eval_authority_widening_detected")
    if eval_result.network_opened or eval_result.handler_executed:
        reasons.append("skill_eval_side_effect_detected")
    if eval_result.credential_material_accessed or not eval_result.no_secret_echo:
        reasons.append("skill_eval_secret_exposure_detected")
    if eval_result.live_production_claimed:
        reasons.append("skill_eval_production_claim_detected")
    return tuple(dict.fromkeys(reasons))


def _record_payload(*, eval_result: SkillEvalResult, eval_ref: str) -> dict[str, JsonValue]:
    return {
        "eval_record_id": _record_id(eval_result=eval_result, eval_ref=eval_ref),
        "eval_ref": eval_ref,
        "candidate_id": eval_result.candidate_id,
        "generated_candidate_id": eval_result.generated_candidate_id,
        "source": eval_result.source,
        "source_candidate_id": eval_result.source_candidate_id,
        "source_record_id": eval_result.source_record_id,
        "decision": eval_result.decision,
        "eval_status": eval_result.eval_status,
        "score": eval_result.score,
        "blocked_reasons": list(eval_result.blocked_reasons),
        "promotion_allowed": False,
        "active_skill_written": False,
        "active_rule_written": False,
        "authority_widened": False,
        "network_opened": False,
        "handler_executed": False,
        "credential_material_accessed": False,
        "live_production_claimed": False,
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


def _result(
    *,
    decision: SkillEvalRegistryDecision,
    path: Path,
    eval_ref: Optional[str] = None,
    eval_result: Optional[SkillEvalResult] = None,
    eval_record_id: Optional[str] = None,
    records: tuple[dict[str, JsonValue], ...] = (),
    record_count: int = 0,
    blocked_reasons: tuple[str, ...] = (),
) -> SkillEvalRegistryResult:
    result = SkillEvalRegistryResult(
        decision=decision,
        eval_record_id=eval_record_id,
        eval_ref=eval_ref,
        record_path=str(path),
        candidate_id=None if eval_result is None else eval_result.candidate_id,
        eval_status=None if eval_result is None else eval_result.eval_status,
        source=None if eval_result is None else eval_result.source,
        record_count=record_count,
        ready_for_review_count=_status_count(records, "ready_for_review"),
        blocked_eval_count=_status_count(records, "blocked"),
        records=records,
        blocked_reasons=blocked_reasons,
        promotion_allowed=False,
        active_skill_written=False,
        active_rule_written=False,
        authority_widened=False,
        network_opened=False,
        handler_executed=False,
        credential_material_accessed=False,
        live_production_claimed=False,
        recommended_next_commands=_recommended_next_commands(decision),
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _status_count(records: tuple[dict[str, JsonValue], ...], status: str) -> int:
    return sum(1 for record in records if record.get("eval_status") == status)


def _record_id(*, eval_result: SkillEvalResult, eval_ref: str) -> str:
    payload = json.dumps(
        {
            "candidate_id": eval_result.candidate_id,
            "eval_ref": eval_ref,
            "eval_status": eval_result.eval_status,
            "score": eval_result.score,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "skill-eval-record-{0}".format(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16])


def _records_path(home: Path) -> Path:
    return home / "skills" / "evals.jsonl"


def _recommended_next_commands(decision: SkillEvalRegistryDecision) -> tuple[str, ...]:
    if decision == "blocked":
        return ("zeus skill-eval --json", "zeus skills --json")
    return ("zeus skill-eval-records --json", "zeus skills --json")


def _no_secret_echo(result: SkillEvalRegistryResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
