from __future__ import annotations

from pathlib import Path
from typing import Final, Literal, Mapping, Optional, Sequence

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from zeus_agent.workloop_runtime import WorkLoopPlan

EvidenceStatus = Literal["passed", "planned_only", "mapped_only", "failed", "missing", "blocked"]
ObligationType = Literal["requirement", "runtime", "gate", "manual_qa"]
_FILE_ARTIFACT_PREFIXES: Final[tuple[str, ...]] = (".omo/", "harness/")
_FILE_ARTIFACT_SUFFIXES: Final[tuple[str, ...]] = (".txt", ".json", ".jsonl", ".md", ".log")
_LOGICAL_EVIDENCE_TARGETS: Final[tuple[str, ...]] = ("main-orchestrator-script-pty",)
_COMMAND_PREFIXES: Final[tuple[str, ...]] = (
    "bash ",
    "git ",
    "make ",
    "python ",
    "python3 ",
    "PYTHONPATH=",
    "pytest ",
    "ruff ",
    "sh ",
    "uv ",
    "env ",
)


def _require_non_empty(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("{0} must be non-empty".format(field_name))
    return text


def _optional_non_empty(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return text


class VerificationObligation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str
    requirement_id: str
    lane_id: str
    obligation_type: ObligationType
    evidence_target: Optional[str] = None
    evidence_status: EvidenceStatus
    failure_reason: Optional[str] = None

    @field_validator("obligation_id", "requirement_id", "lane_id")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("evidence_target", "failure_reason")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _optional_non_empty(value)


class VerificationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verification_obligations_count: int
    passed_obligation_ids: list[str]
    blocked_obligation_ids: list[str]
    blocked_reasons: list[str]
    completion_allowed: bool


class VerificationEngine:
    def evaluate(
        self,
        plan: WorkLoopPlan,
        obligations: Sequence[VerificationObligation],
        *,
        required_obligation_ids: Optional[Sequence[str]] = None,
        require_existing_artifacts: bool = False,
        artifact_root: Optional[Path] = None,
        required_artifact_markers: Optional[Mapping[str, Sequence[str]]] = None,
    ) -> VerificationSummary:
        blocked_reasons = list(plan.blocked_reasons)
        blocked_obligation_ids: list[str] = []
        passed_obligation_ids: list[str] = []
        observed_obligation_ids: set[str] = set()

        for obligation in obligations:
            observed_obligation_ids.add(obligation.obligation_id)
            if obligation.evidence_status == "passed" and obligation.evidence_target is not None:
                if require_existing_artifacts and _missing_evidence_artifact(
                    obligation.evidence_target,
                    artifact_root,
                ):
                    blocked_obligation_ids.append(obligation.obligation_id)
                    blocked_reasons.append(
                        "obligation:{0}:missing_evidence_artifact:{1}".format(
                            obligation.obligation_id,
                            obligation.evidence_target,
                        )
                    )
                    continue
                missing_markers = _missing_required_artifact_markers(
                    obligation,
                    artifact_root,
                    required_artifact_markers or {},
                )
                if missing_markers:
                    blocked_obligation_ids.append(obligation.obligation_id)
                    blocked_reasons.extend(
                        "obligation:{0}:missing_evidence_marker:{1}".format(
                            obligation.obligation_id,
                            marker,
                        )
                        for marker in missing_markers
                    )
                    continue
                passed_obligation_ids.append(obligation.obligation_id)
                continue
            blocked_obligation_ids.append(obligation.obligation_id)
            blocked_reasons.extend(_obligation_blocked_reasons(obligation))

        for missing_id in _missing_obligation_ids(
            plan,
            obligations,
            observed_obligation_ids,
            required_obligation_ids,
        ):
            blocked_obligation_ids.append(missing_id)
            blocked_reasons.append("obligation:{0}:missing".format(missing_id))

        cleaned_blocked_reasons = _dedupe_preserve_order(blocked_reasons)
        cleaned_blocked_ids = _dedupe_preserve_order(blocked_obligation_ids)
        return VerificationSummary(
            verification_obligations_count=len(obligations),
            passed_obligation_ids=[
                obligation_id
                for obligation_id in _dedupe_preserve_order(passed_obligation_ids)
                if obligation_id not in cleaned_blocked_ids
            ],
            blocked_obligation_ids=cleaned_blocked_ids,
            blocked_reasons=cleaned_blocked_reasons,
            completion_allowed=not cleaned_blocked_reasons,
        )


def _obligation_blocked_reasons(obligation: VerificationObligation) -> list[str]:
    reasons: list[str] = []
    if obligation.evidence_target is None:
        reasons.append("obligation:{0}:missing_evidence_target".format(obligation.obligation_id))
    if obligation.evidence_status != "passed":
        reasons.append(
            "obligation:{0}:{1}".format(
                obligation.obligation_id,
                obligation.evidence_status,
            )
        )
    return reasons


def _missing_evidence_artifact(target: str, artifact_root: Optional[Path]) -> bool:
    if not _is_file_like_evidence_target(target):
        return False
    return not _resolved_artifact_path(target, artifact_root).exists()


def _missing_required_artifact_markers(
    obligation: VerificationObligation,
    artifact_root: Optional[Path],
    required_artifact_markers: Mapping[str, Sequence[str]],
) -> list[str]:
    target = obligation.evidence_target
    if target is None or not _is_file_like_evidence_target(target):
        return []
    markers = required_artifact_markers.get(
        obligation.obligation_id,
        required_artifact_markers.get(target, ()),
    )
    if not markers:
        return []
    artifact_path = _resolved_artifact_path(target, artifact_root)
    if not artifact_path.exists():
        return []
    contents = artifact_path.read_text(encoding="utf-8", errors="replace")
    return [marker for marker in markers if marker not in contents]


def _is_file_like_evidence_target(target: str) -> bool:
    if target in _LOGICAL_EVIDENCE_TARGETS:
        return False
    if "::" in target:
        return False
    if target.startswith(_COMMAND_PREFIXES):
        return False
    filesystem_target = _filesystem_evidence_target(target)
    artifact_path = Path(filesystem_target)
    return (
        artifact_path.is_absolute()
        or filesystem_target.startswith(_FILE_ARTIFACT_PREFIXES)
        or filesystem_target.endswith(_FILE_ARTIFACT_SUFFIXES)
        or "/" in filesystem_target
        or "\\" in filesystem_target
    )


def _filesystem_evidence_target(target: str) -> str:
    return target.split("#", maxsplit=1)[0]


def _resolved_artifact_path(target: str, artifact_root: Optional[Path]) -> Path:
    artifact_path = Path(_filesystem_evidence_target(target))
    if artifact_path.is_absolute():
        return artifact_path
    return (artifact_root or Path.cwd()) / artifact_path


def _missing_obligation_ids(
    plan: WorkLoopPlan,
    obligations: Sequence[VerificationObligation],
    observed_obligation_ids: set[str],
    required_obligation_ids: Optional[Sequence[str]],
) -> list[str]:
    if required_obligation_ids is not None:
        return [
            obligation_id
            for obligation_id in required_obligation_ids
            if obligation_id not in observed_obligation_ids
        ]
    observed_requirement_ids = {obligation.requirement_id for obligation in obligations}
    return [
        "requirement:{0}".format(requirement_id)
        for requirement_id in plan.acceptance_criteria
        if requirement_id not in observed_requirement_ids
    ]


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = _require_non_empty(value, "values")
        if text not in seen:
            seen.add(text)
            cleaned.append(text)
    return cleaned
