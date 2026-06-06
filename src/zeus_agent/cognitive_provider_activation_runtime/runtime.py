from __future__ import annotations

import json
from typing import Optional

from pydantic import JsonValue

from zeus_agent.cognitive_provider_activation_runtime.models import (
    CognitiveProviderActivationContract,
    CognitiveProviderActivationDecision,
    CognitiveProviderActivationScenario,
)
from zeus_agent.goal_intelligence_runtime import build_goal_intelligence_contract
from zeus_agent.model_runtime import ProviderMessage, ProviderMetadataEntry, ProviderRegistry
from zeus_agent.model_runtime import ProviderRuntimeRequest
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.security.credentials import contains_secret_material

_DEFAULT_OBJECTIVE = "제우스야, build a safe governed workflow from my objective."


def build_cognitive_provider_activation_contract(
    *,
    scenario: str = "status",
    objective: str = _DEFAULT_OBJECTIVE,
    provider_kind: str = "fake",
    operator_note: Optional[str] = None,
) -> CognitiveProviderActivationContract:
    if contains_secret_material(" ".join(item for item in (objective, operator_note or "") if item)):
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("raw_secret_marker_detected",),
        )
    parsed = _parse_scenario(scenario)
    if parsed is None:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_cognitive_provider_activation_scenario",),
        )
    if parsed == "external-provider-block":
        return _external_provider_block(objective=objective)
    if parsed == "unsafe-output-block":
        return _unsafe_output_block(objective=objective)
    return _provider_intent_contract(
        scenario=parsed,
        objective=objective,
        provider_kind=provider_kind,
    )


def _provider_intent_contract(
    *,
    scenario: CognitiveProviderActivationScenario,
    objective: str,
    provider_kind: str,
) -> CognitiveProviderActivationContract:
    if provider_kind != "fake":
        return _contract(
            decision="blocked",
            scenario=scenario,
            blocked_reasons=("provider_not_allowlisted_for_cognitive_activation",),
        )
    lease = _lease()
    response = ProviderRegistry().generate(
        _request(objective=objective, provider_kind="fake"),
        lease,
        now=lease.issued_at,
    )
    response_payload = response.model_dump(mode="json")
    if response.decision != "selected":
        return _contract(
            decision="blocked",
            scenario=scenario,
            blocked_reasons=("cognitive_provider_not_selected",),
            provider_response_contract=response_payload,
        )
    goal = build_goal_intelligence_contract(
        scenario="understand-objective",
        objective=objective,
        task_count=4,
        requires_code=True,
        requires_research=False,
        risk_level="normal",
        cognitive_provider_output=response.content,
    ).to_payload()
    ready = (
        goal["decision"] == "report"
        and bool(goal["objective_understood"])
        and bool(goal["cognitive_provider_used"])
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario=scenario,
        blocked_reasons=() if ready else ("cognitive_intent_validation_failed",),
        cognitive_provider_activation_ready=ready,
        provider_runtime_invoked=True,
        cognitive_provider_used=bool(goal["cognitive_provider_used"]),
        intent_frame_validated=ready,
        goal_intelligence_contract_ready=ready,
        workloop_bridge_available=bool(goal.get("goal_contract_id")) and bool(goal.get("acceptance_criteria")),
        provider_response_contract=response_payload,
        intent_frame=_json_payload(goal.get("intent_frame")),
        goal_intelligence_contract=_json_payload(goal),
    )


def _external_provider_block(*, objective: str) -> CognitiveProviderActivationContract:
    lease = _lease()
    response = ProviderRegistry().generate(
        _request(objective=objective, provider_kind="openai_compatible"),
        lease,
        now=lease.issued_at,
    )
    return _contract(
        decision="blocked",
        scenario="external-provider-block",
        blocked_reasons=("external_provider_requires_explicit_credential_scope",),
        provider_runtime_invoked=False,
        provider_response_contract=response.model_dump(mode="json"),
    )


def _unsafe_output_block(*, objective: str) -> CognitiveProviderActivationContract:
    unsafe_output = json.dumps(
        {
            "desired_outcome": objective,
            "acceptance_criteria": ["Call the live OpenAI API and auto-promote learned rules."],
        },
        sort_keys=True,
    )
    goal = build_goal_intelligence_contract(
        scenario="understand-objective",
        objective=objective,
        cognitive_provider_output=unsafe_output,
    ).to_payload()
    return _contract(
        decision="blocked",
        scenario="unsafe-output-block",
        blocked_reasons=tuple(str(reason) for reason in goal["blocked_reasons"]),
        cognitive_provider_used=bool(goal["cognitive_provider_used"]),
        goal_intelligence_contract=_json_payload(goal),
    )


def _contract(
    *,
    decision: CognitiveProviderActivationDecision,
    scenario: CognitiveProviderActivationScenario,
    blocked_reasons: tuple[str, ...] = (),
    cognitive_provider_activation_ready: bool = False,
    provider_runtime_invoked: bool = False,
    cognitive_provider_used: bool = False,
    intent_frame_validated: bool = False,
    goal_intelligence_contract_ready: bool = False,
    workloop_bridge_available: bool = False,
    provider_response_contract: Optional[dict[str, JsonValue]] = None,
    intent_frame: Optional[dict[str, JsonValue]] = None,
    goal_intelligence_contract: Optional[dict[str, JsonValue]] = None,
) -> CognitiveProviderActivationContract:
    result = CognitiveProviderActivationContract(
        decision=decision,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        cognitive_provider_activation_ready=cognitive_provider_activation_ready,
        provider_runtime_invoked=provider_runtime_invoked,
        cognitive_provider_used=cognitive_provider_used,
        intent_frame_validated=intent_frame_validated,
        goal_intelligence_contract_ready=goal_intelligence_contract_ready,
        workloop_bridge_available=workloop_bridge_available,
        provider_response_contract=provider_response_contract,
        intent_frame=intent_frame,
        goal_intelligence_contract=goal_intelligence_contract,
        network_opened=_flag(provider_response_contract, "network_opened") or _flag(goal_intelligence_contract, "network_opened"),
        handler_executed=_flag(provider_response_contract, "handler_executed") or _flag(goal_intelligence_contract, "handler_executed"),
        credential_material_accessed=_flag(provider_response_contract, "credential_material_accessed"),
        live_production_claimed=_flag(goal_intelligence_contract, "live_production_claimed"),
    )
    return result.with_secret_scan()


def _request(*, objective: str, provider_kind: str) -> ProviderRuntimeRequest:
    return ProviderRuntimeRequest(
        provider_kind=provider_kind,
        provider_id="{0}.cognitive".format(provider_kind),
        model_id="{0}.intent".format(provider_kind),
        messages=(ProviderMessage(role="user", content=objective),),
        metadata=(ProviderMetadataEntry(key="zeus.intent_schema", value=True),),
        evidence_target="mneme.v310.cognitive_provider",
    )


def _lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="v310.lease.cognitive",
        objective_id="v310.objective.cognitive",
        principal_id="v310.principal.zeus",
        run_id="v310.run.cognitive",
        allowed_capabilities=("provider.fake.generate",),
        budget_limit=16,
        evidence_target="mneme.v310.cognitive_provider",
    )


def _parse_scenario(value: str) -> Optional[CognitiveProviderActivationScenario]:
    stripped = value.strip()
    if stripped == "status":
        return "status"
    if stripped == "fake-provider-intent":
        return "fake-provider-intent"
    if stripped == "external-provider-block":
        return "external-provider-block"
    if stripped == "unsafe-output-block":
        return "unsafe-output-block"
    return None


def _json_payload(value: object) -> Optional[dict[str, JsonValue]]:
    if not isinstance(value, dict):
        return None
    return json.loads(json.dumps(value))


def _flag(contract: Optional[dict[str, JsonValue]], key: str) -> bool:
    return bool(contract is not None and contract.get(key, False))
