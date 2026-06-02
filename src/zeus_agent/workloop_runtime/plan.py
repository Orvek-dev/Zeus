from __future__ import annotations

from typing import Optional, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class ObjectiveContractLike(Protocol):
    goal_contract_id: str
    normalized_goal: str
    deliverables: Sequence[str]
    acceptance_criteria: Sequence[str]


class VerificationObligationLike(Protocol):
    obligation_id: str


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


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = _require_non_empty(value, "values")
        if text not in seen:
            seen.add(text)
            cleaned.append(text)
    return cleaned


class OrchestrationLane(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lane_id: str
    owned_paths: list[str] = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)
    stop_condition: Optional[str] = None
    manual_qa_channel: str
    evidence_target: Optional[str] = None

    @field_validator("lane_id", "manual_qa_channel")
    @classmethod
    def _validate_required_text(cls, value: str, info: ValidationInfo) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("owned_paths")
    @classmethod
    def _validate_owned_paths(cls, values: list[str]) -> list[str]:
        return _dedupe_preserve_order(values)

    @field_validator("depends_on", "blocks")
    @classmethod
    def _validate_edges(cls, values: list[str]) -> list[str]:
        return sorted(_dedupe_preserve_order(values))

    @field_validator("stop_condition", "evidence_target")
    @classmethod
    def _validate_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _optional_non_empty(value)


class LaneDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lane_id: str
    depends_on: list[str]
    blocks: list[str]


class WorkLoopPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    work_loop_id: str
    goal_contract_id: str
    normalized_goal: str
    deliverables: list[str]
    acceptance_criteria: list[str]
    lanes: list[OrchestrationLane] = Field(min_length=1)
    verification_obligations_count: int
    blocked_reasons: list[str]
    completion_allowed: bool

    def serialize_lane_dependencies(self) -> list[LaneDependency]:
        return [
            LaneDependency(
                lane_id=lane.lane_id,
                depends_on=sorted(lane.depends_on),
                blocks=sorted(lane.blocks),
            )
            for lane in sorted(self.lanes, key=lambda item: item.lane_id)
        ]


class WorkLoopBuilder:
    def build(
        self,
        *,
        lanes: Sequence[OrchestrationLane],
        contract: Optional[ObjectiveContractLike] = None,
        goal_contract_id: Optional[str] = None,
        normalized_goal: Optional[str] = None,
        deliverables: Optional[Sequence[str]] = None,
        acceptance_criteria: Optional[Sequence[str]] = None,
        verification_obligations: Optional[Sequence[VerificationObligationLike]] = None,
        verification_obligations_count: Optional[int] = None,
        work_loop_id: Optional[str] = None,
    ) -> WorkLoopPlan:
        resolved_goal_contract_id = _resolve_goal_contract_id(contract, goal_contract_id)
        resolved_normalized_goal = _resolve_normalized_goal(contract, normalized_goal)
        resolved_deliverables = _resolve_sequence(contract, deliverables, "deliverables")
        resolved_acceptance_criteria = _resolve_sequence(
            contract,
            acceptance_criteria,
            "acceptance_criteria",
        )
        resolved_lanes = sorted(list(lanes), key=lambda lane: lane.lane_id)
        obligation_count = _resolve_obligation_count(
            verification_obligations,
            verification_obligations_count,
        )
        blocked_reasons = [
            *_lane_blocked_reasons(resolved_lanes),
            *_ownership_blocked_reasons(resolved_lanes),
        ]
        if obligation_count == 0:
            blocked_reasons.append("plan:missing_verification_obligations")

        return WorkLoopPlan(
            work_loop_id=work_loop_id
            or "workloop-{0}".format(resolved_goal_contract_id),
            goal_contract_id=resolved_goal_contract_id,
            normalized_goal=resolved_normalized_goal,
            deliverables=resolved_deliverables,
            acceptance_criteria=resolved_acceptance_criteria,
            lanes=resolved_lanes,
            verification_obligations_count=obligation_count,
            blocked_reasons=blocked_reasons,
            completion_allowed=not blocked_reasons,
        )


def build_work_loop_plan(
    *,
    lanes: Sequence[OrchestrationLane],
    contract: Optional[ObjectiveContractLike] = None,
    goal_contract_id: Optional[str] = None,
    normalized_goal: Optional[str] = None,
    deliverables: Optional[Sequence[str]] = None,
    acceptance_criteria: Optional[Sequence[str]] = None,
    verification_obligations: Optional[Sequence[VerificationObligationLike]] = None,
    verification_obligations_count: Optional[int] = None,
    work_loop_id: Optional[str] = None,
) -> WorkLoopPlan:
    return WorkLoopBuilder().build(
        lanes=lanes,
        contract=contract,
        goal_contract_id=goal_contract_id,
        normalized_goal=normalized_goal,
        deliverables=deliverables,
        acceptance_criteria=acceptance_criteria,
        verification_obligations=verification_obligations,
        verification_obligations_count=verification_obligations_count,
        work_loop_id=work_loop_id,
    )


def _resolve_goal_contract_id(
    contract: Optional[ObjectiveContractLike],
    explicit: Optional[str],
) -> str:
    if explicit is not None:
        return _require_non_empty(explicit, "goal_contract_id")
    if contract is None:
        raise ValueError("goal_contract_id_required")
    return _require_non_empty(contract.goal_contract_id, "goal_contract_id")


def _resolve_normalized_goal(
    contract: Optional[ObjectiveContractLike],
    explicit: Optional[str],
) -> str:
    if explicit is not None:
        return _require_non_empty(explicit, "normalized_goal")
    if contract is None:
        raise ValueError("normalized_goal_required")
    return _require_non_empty(contract.normalized_goal, "normalized_goal")


def _resolve_sequence(
    contract: Optional[ObjectiveContractLike],
    explicit: Optional[Sequence[str]],
    field_name: str,
) -> list[str]:
    if explicit is not None:
        return _dedupe_preserve_order(explicit)
    if contract is None:
        return []
    sequences = {
        "deliverables": contract.deliverables,
        "acceptance_criteria": contract.acceptance_criteria,
    }
    selected = sequences.get(field_name)
    if selected is None:
        raise ValueError("unsupported_sequence_field:{0}".format(field_name))
    return _dedupe_preserve_order(selected)


def _resolve_obligation_count(
    obligations: Optional[Sequence[VerificationObligationLike]],
    explicit_count: Optional[int],
) -> int:
    if explicit_count is not None:
        if explicit_count < 0:
            raise ValueError("verification_obligations_count_must_be_non_negative")
        return explicit_count
    if obligations is None:
        return 0
    return len(obligations)


def _lane_blocked_reasons(lanes: Sequence[OrchestrationLane]) -> list[str]:
    blocked: list[str] = []
    for lane in sorted(lanes, key=lambda item: item.lane_id):
        if lane.evidence_target is None:
            blocked.append("lane:{0}:missing_evidence_target".format(lane.lane_id))
        if lane.stop_condition is None:
            blocked.append("lane:{0}:missing_stop_condition".format(lane.lane_id))
    return blocked


def _ownership_blocked_reasons(lanes: Sequence[OrchestrationLane]) -> list[str]:
    owners: dict[str, str] = {}
    blocked: list[str] = []
    for lane in sorted(lanes, key=lambda item: item.lane_id):
        for owned_path in lane.owned_paths:
            previous = owners.get(owned_path)
            if previous is not None:
                blocked.append(
                    "owned_path:{0}:claimed_by:{1},{2}".format(
                        owned_path,
                        previous,
                        lane.lane_id,
                    )
                )
            owners[owned_path] = lane.lane_id
    return blocked
