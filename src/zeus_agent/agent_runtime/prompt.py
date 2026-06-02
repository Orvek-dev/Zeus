from __future__ import annotations

import re
from typing import Final

from pydantic import BaseModel, ConfigDict

from zeus_agent.kernel.contracts import ExecutionSpec, GoalContract

REDACTED_SECRET: Final = "[REDACTED_SECRET]"
_SECRET_LIKE_PATTERN: Final[re.Pattern[str]] = re.compile(r"\bsk-[A-Za-z0-9_-]+\b")


class PromptContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stable: str
    context: str
    volatile: str
    visible_tools: list[str]


def build_prompt_context(
    contract: GoalContract,
    execution: ExecutionSpec,
    visible_tools: list[str],
    profile: str,
) -> PromptContext:
    goal_contract_id = _redact_secret_like(contract.goal_contract_id)
    normalized_goal = _redact_secret_like(contract.normalized_goal)
    acceptance_criteria = _redact_secret_like_values(contract.acceptance_criteria)
    run_id = _redact_secret_like(execution.run_id)
    profile_label = _redact_secret_like(profile)
    tool_labels = _redact_secret_like_values(visible_tools)
    stable = "\n".join(
        [
            "goal_contract_id={0}".format(goal_contract_id),
            "normalized_goal={0}".format(normalized_goal),
            "acceptance_criteria={0}".format(",".join(acceptance_criteria)),
        ]
    )
    context = "\n".join(
        [
            "run_id={0}".format(run_id),
            "execution_mode={0}".format(execution.execution_mode.value),
            "profile={0}".format(profile_label),
        ]
    )
    volatile = "visible_tools={0}".format(",".join(tool_labels))
    return PromptContext(
        stable=stable,
        context=context,
        volatile=volatile,
        visible_tools=tool_labels,
    )


def _redact_secret_like(value: str) -> str:
    return _SECRET_LIKE_PATTERN.sub(REDACTED_SECRET, value)


def _redact_secret_like_values(values: list[str]) -> list[str]:
    return [_redact_secret_like(value) for value in values]
