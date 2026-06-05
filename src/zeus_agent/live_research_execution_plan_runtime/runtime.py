from __future__ import annotations

import hashlib
import json
from typing import Optional

from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyResult
from zeus_agent.live_research_execution_plan_runtime.models import LiveResearchExecutionPlanResult
from zeus_agent.live_research_source_config_runtime import LiveResearchSourceConfigResult


class LiveResearchExecutionPlanRuntime:
    def plan(
        self,
        *,
        source_config: LiveResearchSourceConfigResult,
        policy: LiveResearchActivationPolicyResult,
        execution_ref: str,
    ) -> LiveResearchExecutionPlanResult:
        reasons = _blocked_reasons(source_config=source_config, policy=policy)
        planned = len(reasons) == 0
        return LiveResearchExecutionPlanResult(
            decision="planned" if planned else "blocked",
            execution_id=_execution_id(execution_ref, policy.policy_id) if planned else None,
            execution_ref=execution_ref,
            adapter_id=source_config.adapter_id,
            source_id=source_config.source_id,
            endpoint=source_config.endpoint,
            policy_id=policy.policy_id,
            source_config_id=source_config.config_id,
            source_pin_ref=policy.source_pin_ref,
            max_results=policy.max_results,
            rate_limit_per_minute=policy.rate_limit_per_minute,
            blocked_reasons=tuple(dict.fromkeys(reasons)),
            source_config_bound=source_config.decision == "configured",
            activation_policy_bound=policy.decision == "activation_planned",
            endpoint_bound=source_config.endpoint_bound,
            source_pin_bound=policy.source_pin_bound,
            approval_bound=policy.approval_bound,
            live_search_allowed=policy.live_search_allowed and planned,
            real_fetcher_available=source_config.real_fetcher_available,
            production_fetcher_configured=source_config.production_fetcher_configured,
        )


def _blocked_reasons(
    *,
    source_config: LiveResearchSourceConfigResult,
    policy: LiveResearchActivationPolicyResult,
) -> list[str]:
    reasons: list[str] = []
    if source_config.decision != "configured":
        reasons.append("live_research_source_config_not_configured")
    if policy.decision != "activation_planned":
        reasons.append("live_research_activation_not_planned")
    if source_config.source_id != policy.source_id:
        reasons.append("live_research_source_mismatch")
    if not source_config.endpoint_bound:
        reasons.append("live_research_endpoint_not_bound")
    if not source_config.real_fetcher_available:
        reasons.append("live_research_real_fetcher_unavailable")
    return reasons


def _execution_id(execution_ref: str, policy_id: Optional[str]) -> str:
    payload = {"execution_ref": execution_ref, "policy_id": policy_id}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-execution-plan-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])
