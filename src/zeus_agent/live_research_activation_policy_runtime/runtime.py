from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.security.credentials import redact_secret_spans

LiveResearchActivationPolicyDecision = Literal["policy_ready", "activation_planned", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_LIVE_CAPABLE_SOURCES: Final[tuple[str, ...]] = ("web", "github", "community")
_KNOWN_SOURCES: Final[tuple[str, ...]] = ("web", "github", "developer-docs", "community")
_MAX_RESULTS_LIMIT: Final = 10
_RATE_LIMIT_PER_MINUTE: Final = 60


class LiveResearchActivationPolicyResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveResearchActivationPolicyDecision
    policy_id: Optional[str]
    source_id: str
    query: str
    approval_ref: Optional[str]
    source_pin_ref: Optional[str]
    max_results: int
    rate_limit_per_minute: int
    blocked_reasons: tuple[str, ...] = ()
    source_known: bool = False
    live_capable_source: bool = False
    source_pin_required: bool = True
    approval_bound: bool = False
    source_pin_bound: bool = False
    live_search_requested: bool = False
    live_search_allowed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    client_constructed: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveResearchActivationPolicyRuntime:
    def plan(
        self,
        *,
        source_id: str,
        query: str,
        live_search_requested: bool = False,
        approval_ref: Optional[str] = None,
        source_pin_ref: Optional[str] = None,
        max_results: int = 5,
        rate_limit_per_minute: int = 30,
    ) -> LiveResearchActivationPolicyResult:
        safe_source = source_id.strip()
        safe_query = redact_secret_spans(query.strip())
        safe_approval = None if approval_ref is None else approval_ref.strip() or None
        safe_pin = None if source_pin_ref is None else source_pin_ref.strip() or None
        reasons = _policy_reasons(
            source_id=safe_source,
            live_search_requested=live_search_requested,
            approval_ref=safe_approval,
            source_pin_ref=safe_pin,
            max_results=max_results,
            rate_limit_per_minute=rate_limit_per_minute,
        )
        decision = _decision(live_search_requested=live_search_requested, blocked_reasons=reasons)
        return LiveResearchActivationPolicyResult(
            decision=decision,
            policy_id=_policy_id(safe_source, safe_query, safe_pin) if not reasons else None,
            source_id=safe_source,
            query=safe_query,
            approval_ref=safe_approval,
            source_pin_ref=safe_pin,
            max_results=max_results,
            rate_limit_per_minute=rate_limit_per_minute,
            blocked_reasons=reasons,
            source_known=safe_source in _KNOWN_SOURCES,
            live_capable_source=safe_source in _LIVE_CAPABLE_SOURCES,
            approval_bound=safe_approval is not None,
            source_pin_bound=safe_pin is not None,
            live_search_requested=live_search_requested,
            live_search_allowed=decision == "activation_planned",
            network_opened=False,
            handler_executed=False,
            client_constructed=False,
            credential_material_accessed=False,
            live_production_claimed=False,
            recommended_next_commands=_recommended_next_commands(decision),
        )


def _policy_reasons(
    *,
    source_id: str,
    live_search_requested: bool,
    approval_ref: Optional[str],
    source_pin_ref: Optional[str],
    max_results: int,
    rate_limit_per_minute: int,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if source_id == "":
        reasons.append("source_id_required")
    if source_id not in _KNOWN_SOURCES:
        reasons.append("unknown_research_source")
    if live_search_requested and source_id not in _LIVE_CAPABLE_SOURCES:
        reasons.append("research_source_not_live_capable")
    if live_search_requested and approval_ref is None:
        reasons.append("live_research_requires_approval")
    if live_search_requested and source_pin_ref is None:
        reasons.append("source_pin_ref_required")
    if max_results < 1:
        reasons.append("max_results_required")
    if max_results > _MAX_RESULTS_LIMIT:
        reasons.append("max_results_limit_exceeded")
    if rate_limit_per_minute < 1:
        reasons.append("rate_limit_required")
    if rate_limit_per_minute > _RATE_LIMIT_PER_MINUTE:
        reasons.append("rate_limit_exceeded")
    return tuple(dict.fromkeys(reasons))


def _decision(
    *,
    live_search_requested: bool,
    blocked_reasons: tuple[str, ...],
) -> LiveResearchActivationPolicyDecision:
    if blocked_reasons:
        return "blocked"
    if live_search_requested:
        return "activation_planned"
    return "policy_ready"


def _policy_id(source_id: str, query: str, source_pin_ref: Optional[str]) -> str:
    payload = {"query": query, "source_id": source_id, "source_pin_ref": source_pin_ref}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-activation-policy-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _recommended_next_commands(decision: LiveResearchActivationPolicyDecision) -> tuple[str, ...]:
    if decision == "activation_planned":
        return ("zeus research-brief --query <query> --json", "zeus live-readiness --json")
    if decision == "policy_ready":
        return ("zeus research --source github --query <query> --json",)
    return ("zeus research --json", "zeus approval-receipt --json")
