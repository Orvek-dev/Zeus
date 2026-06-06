from __future__ import annotations

import json
import re
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from zeus_agent.objective_runtime import ObjectiveCompiler
from zeus_agent.goal_intelligence_runtime.policy import unsafe_policy_reasons

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_MIN_CONFIDENCE: Final = 0.75
_OUTCOME_PATTERN: Final = re.compile(r"\boutcome\s+is\s+(?P<value>.+)", re.IGNORECASE)
_VAGUE_WORDS: Final[frozenset[str]] = frozenset(
    {"make", "it", "better", "improve", "fix", "stuff", "thing", "this", "zeus"}
)


class IntentFrame(BaseModel):
    model_config = _MODEL_CONFIG

    desired_outcome: str
    acceptance_criteria: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("desired_outcome")
    @classmethod
    def _validate_desired_outcome(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("desired_outcome must be non-empty")
        return text

    @field_validator("acceptance_criteria", "constraints", "entities", "assumptions", "unknowns")
    @classmethod
    def _validate_text_tuple(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        cleaned: list[str] = []
        for value in values:
            text = value.strip()
            if text:
                cleaned.append(text)
        return tuple(dict.fromkeys(cleaned))

    @property
    def understood(self) -> bool:
        high_impact_unknowns = {"desired_outcome", "acceptance_criteria", "risk_boundary"}
        return (
            bool(self.acceptance_criteria)
            and self.confidence >= _MIN_CONFIDENCE
            and not high_impact_unknowns.intersection(self.unknowns)
        )


class IntentBuildResult(BaseModel):
    model_config = _MODEL_CONFIG

    frame: IntentFrame
    blocked_reasons: tuple[str, ...] = ()
    cognitive_provider_used: bool = False


class CognitiveProviderFrame(BaseModel):
    model_config = _MODEL_CONFIG

    desired_outcome: str
    acceptance_criteria: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)

    @field_validator("desired_outcome")
    @classmethod
    def _validate_desired_outcome(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("desired_outcome must be non-empty")
        return text

    @field_validator("acceptance_criteria", "constraints", "entities")
    @classmethod
    def _validate_text_list(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned and values:
            raise ValueError("tuple values must be non-empty")
        return cleaned


def build_intent_frame(
    *,
    objective: str,
    task_count: int,
    requires_code: bool,
    requires_research: bool,
    risk_level: str,
    interview_answers: tuple[str, ...] = (),
    cognitive_provider_output: Optional[str] = None,
) -> IntentBuildResult:
    if cognitive_provider_output is not None:
        return _frame_from_cognitive_output(cognitive_provider_output)
    desired = objective.strip()
    answers = tuple(answer.strip() for answer in interview_answers if answer.strip())
    desired = _desired_from_answers(desired, answers)
    constraints = _constraints(objective=objective, answers=answers, risk_level=risk_level)
    acceptance = _acceptance_criteria(
        objective=desired,
        answers=answers,
        task_count=task_count,
        requires_code=requires_code,
        requires_research=requires_research,
        constraints=constraints,
    )
    entities = _entities(objective=objective, requires_code=requires_code, requires_research=requires_research)
    unknowns = _unknowns(objective=desired, acceptance_criteria=acceptance, constraints=constraints)
    confidence = _confidence(unknowns=unknowns, acceptance_criteria=acceptance, answers=answers)
    return IntentBuildResult(
        frame=IntentFrame(
            desired_outcome=desired or "Unspecified Zeus objective",
            acceptance_criteria=acceptance,
            constraints=constraints,
            entities=entities,
            assumptions=(),
            unknowns=unknowns,
            confidence=confidence,
        )
    )


def interview_questions_for(frame: IntentFrame) -> tuple[str, ...]:
    question_by_unknown: Final[dict[str, str]] = {
        "desired_outcome": "What concrete outcome should the workflow produce?",
        "acceptance_criteria": "What observable evidence should prove completion?",
        "constraints": "Which constraints, approvals, or rollback rules must bound the work?",
        "entities": "Which systems, tools, repos, or providers are in scope?",
        "risk_boundary": "Which actions are unsafe without human approval?",
    }
    questions: list[str] = []
    for unknown in frame.unknowns:
        questions.append(
            question_by_unknown.get(unknown, "Which missing detail would change the execution plan?")
        )
    return tuple(dict.fromkeys(questions))


def residual_assumptions_for(frame: IntentFrame) -> tuple[str, ...]:
    return tuple("Assumed {0} can be refined during execution.".format(unknown) for unknown in frame.unknowns)


def _frame_from_cognitive_output(output: str) -> IntentBuildResult:
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        return IntentBuildResult(
            frame=IntentFrame(
                desired_outcome="[blocked-cognitive-output]",
                unknowns=("desired_outcome", "acceptance_criteria"),
                confidence=0.0,
            ),
            blocked_reasons=("cognitive_output_malformed",),
            cognitive_provider_used=True,
        )
    if not isinstance(parsed, dict):
        return IntentBuildResult(
            frame=IntentFrame(desired_outcome="[blocked-cognitive-output]", confidence=0.0),
            blocked_reasons=("cognitive_output_malformed",),
            cognitive_provider_used=True,
        )
    try:
        provider_frame = CognitiveProviderFrame.model_validate(parsed)
    except ValidationError:
        return IntentBuildResult(
            frame=IntentFrame(desired_outcome="[blocked-cognitive-output]", confidence=0.0),
            blocked_reasons=("cognitive_output_malformed",),
            cognitive_provider_used=True,
        )
    text = json.dumps(provider_frame.model_dump(mode="json"), sort_keys=True)
    if unsafe_policy_reasons(text):
        return IntentBuildResult(
            frame=IntentFrame(desired_outcome="[blocked-cognitive-output]", confidence=0.0),
            blocked_reasons=("cognitive_output_unsafe",),
            cognitive_provider_used=True,
        )
    return IntentBuildResult(
        frame=IntentFrame(
            desired_outcome=provider_frame.desired_outcome,
            acceptance_criteria=tuple(provider_frame.acceptance_criteria),
            constraints=tuple(provider_frame.constraints),
            entities=tuple(provider_frame.entities),
            confidence=0.8,
        ),
        cognitive_provider_used=True,
    )


def _desired_from_answers(objective: str, answers: tuple[str, ...]) -> str:
    for answer in answers:
        match = _OUTCOME_PATTERN.search(answer)
        if match is not None:
            return match.group("value").strip().rstrip(".")
    return objective


def _acceptance_criteria(
    *,
    objective: str,
    answers: tuple[str, ...],
    task_count: int,
    requires_code: bool,
    requires_research: bool,
    constraints: tuple[str, ...],
) -> tuple[str, ...]:
    criteria = [answer for answer in answers if answer.lower().startswith("complete means")]
    if not _is_vague(objective):
        criteria.append("Observable evidence proves completion for: {0}".format(objective))
    if requires_code:
        criteria.append("Targeted implementation tests pass for the governed workflow.")
    if requires_research:
        criteria.append("Research-backed decisions include cited or reviewable source evidence.")
    if any("approval" in item or "lease" in item or "audit" in item for item in constraints):
        criteria.append("Live-capable actions require approval, lease, credential binding, and audit evidence.")
    if task_count >= 4 and not _is_vague(objective):
        criteria.append("Parallel work scopes are split without write conflicts.")
    return tuple(dict.fromkeys(criteria))


def _constraints(*, objective: str, answers: tuple[str, ...], risk_level: str) -> tuple[str, ...]:
    constraints = [answer for answer in answers if answer.lower().startswith("constraints")]
    lowered = " ".join((objective, *answers)).lower()
    for marker in ("secret_ref", "approval", "lease", "audit", "local-first", "no raw secrets", "candidate-only"):
        if marker in lowered:
            constraints.append(marker)
    if risk_level == "high":
        constraints.append("human approval and rollback required")
    return tuple(dict.fromkeys(constraints))


def _entities(*, objective: str, requires_code: bool, requires_research: bool) -> tuple[str, ...]:
    lowered = objective.lower()
    entities: list[str] = []
    for marker in ("zeus", "mcp", "openai", "anthropic", "provider", "gateway", "sandbox", "browser", "terminal"):
        if marker in lowered:
            entities.append(marker)
    if requires_code:
        entities.append("code")
    if requires_research:
        entities.append("research")
    return tuple(dict.fromkeys(entities))


def _unknowns(
    *,
    objective: str,
    acceptance_criteria: tuple[str, ...],
    constraints: tuple[str, ...],
) -> tuple[str, ...]:
    unknowns: list[str] = []
    if _is_vague(objective):
        unknowns.append("desired_outcome")
    if not acceptance_criteria:
        unknowns.append("acceptance_criteria")
    if not constraints:
        unknowns.append("constraints")
    if "live" in objective.lower() and not any("approval" in item or "audit" in item for item in constraints):
        unknowns.append("risk_boundary")
    return tuple(dict.fromkeys(unknowns))


def _confidence(
    *,
    unknowns: tuple[str, ...],
    acceptance_criteria: tuple[str, ...],
    answers: tuple[str, ...],
) -> float:
    score = 0.95 - (0.2 * len(unknowns))
    if acceptance_criteria:
        score += 0.1
    if answers:
        score += min(0.15, 0.05 * len(answers))
    return max(0.0, min(1.0, score))


def _is_vague(objective: str) -> bool:
    words = [word.strip(".,:;!?").lower() for word in objective.split()]
    return len(words) < 5 or all(word in _VAGUE_WORDS for word in words)
