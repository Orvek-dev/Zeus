from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.skill_cockpit_runtime import SkillCockpitRuntime
from zeus_agent.skill_eval_runtime.models import SkillEvalCheck, SkillEvalResult

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
_SAFE_REVIEW_BLOCKERS: Final[set[str]] = {"explicit_review_required"}


class SkillEvalRuntime:
    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = home

    def evaluate(self, *, candidate_id: str) -> SkillEvalResult:
        cockpit = SkillCockpitRuntime(self.home).build(candidate_id=candidate_id)
        selected = cockpit.selected_candidate
        if selected is None:
            return _blocked_result(candidate_id=candidate_id, reasons=cockpit.blocked_reasons)
        checks = _checks(selected)
        score = sum(check.points for check in checks if check.passed)
        unsafe_reasons = _unsafe_reasons(selected)
        eval_status = "blocked" if unsafe_reasons or score < 80 else "ready_for_review"
        result = SkillEvalResult(
            decision="evaluated",
            eval_status=eval_status,
            candidate_id=_text(selected.get("candidate_id")),
            generated_candidate_id=_text(selected.get("generated_candidate_id")),
            source=_text(selected.get("source")),
            source_candidate_id=_text(selected.get("source_candidate_id")),
            source_record_id=_text(selected.get("source_record_id")),
            score=score,
            checks=checks,
            blocked_reasons=unsafe_reasons,
            recommended_next_commands=_recommended_next_commands(eval_status),
            promotion_allowed=False,
            active_skill_written=False,
            active_rule_written=False,
            authority_widened=False,
            network_opened=False,
            handler_executed=False,
            credential_material_accessed=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _checks(candidate: dict[str, JsonValue]) -> tuple[SkillEvalCheck, ...]:
    return (
        _check("candidate_selected", True, 10, "candidate was found in the skill cockpit"),
        _check(
            "source_evidence_bound",
            bool(candidate.get("source_evidence_ids")),
            20,
            "candidate has source evidence ids",
        ),
        _check(
            "review_gate_present",
            candidate.get("review_status") in {"review_required", "approved_for_promotion"},
            20,
            "candidate requires review or has explicit promotion approval",
        ),
        _check(
            "no_unsafe_blockers",
            not _unsafe_reasons(candidate),
            20,
            "candidate has no unsafe promotion blockers beyond review requirement",
        ),
        _check(
            "no_authority_delta",
            not bool(candidate.get("authority_delta_allowed")) and not bool(candidate.get("authority_widened")),
            10,
            "candidate does not widen authority",
        ),
        _check(
            "no_activation_side_effect",
            _no_activation_side_effect(candidate),
            20,
            "candidate did not activate skills, rules, transport, handlers, or production claims",
        ),
    )


def _check(check_id: str, passed: bool, points: int, reason: str) -> SkillEvalCheck:
    return SkillEvalCheck(check_id=check_id, passed=passed, points=points, reason=reason)


def _unsafe_reasons(candidate: dict[str, JsonValue]) -> tuple[str, ...]:
    raw_reasons = candidate.get("blocked_reasons")
    reasons = raw_reasons if isinstance(raw_reasons, list) else []
    return tuple(
        reason
        for reason in reasons
        if isinstance(reason, str) and reason not in _SAFE_REVIEW_BLOCKERS
    )


def _no_activation_side_effect(candidate: dict[str, JsonValue]) -> bool:
    return not any(
        bool(candidate.get(key))
        for key in (
            "promoted",
            "active_skill_written",
            "active_rule_written",
            "network_opened",
            "handler_executed",
            "live_production_claimed",
        )
    )


def _blocked_result(*, candidate_id: str, reasons: tuple[str, ...]) -> SkillEvalResult:
    result = SkillEvalResult(
        decision="blocked",
        eval_status="blocked",
        candidate_id=candidate_id,
        blocked_reasons=reasons,
        recommended_next_commands=("zeus skills --json",),
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _recommended_next_commands(eval_status: str) -> tuple[str, ...]:
    if eval_status == "ready_for_review":
        return ("zeus skills --json", "zeus security --json")
    return ("zeus skills --json", "zeus security --json", "zeus remember --json")


def _text(value: JsonValue) -> Optional[str]:
    return value if isinstance(value, str) and value.strip() else None


def _no_secret_echo(result: SkillEvalResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
