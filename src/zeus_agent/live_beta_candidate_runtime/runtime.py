from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime
from zeus_agent.live_smoke_runtime import LiveOptInSmokeScenario
from zeus_agent.security.credentials import redact_secret_spans


LiveBetaCandidateDecision = Literal["report", "blocked"]
_SCENARIO_ERROR: Final = "scenario must be one of: happy, blocked"

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_TARGET_VERSION: Final = "v1.0.0-rc"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.0.0-rc.live_beta_candidate"
_REQUIRED_CONTROLS: Final[tuple[str, ...]] = (
    "objective_contract",
    "runtime_lease",
    "approval_receipt",
    "credential_scope",
    "sandbox_or_loopback",
    "audit_evidence",
    "rollback_path",
    "independent_review",
)
_RECOMMENDED_NEXT_COMMANDS: Final[tuple[str, ...]] = (
    "zeus live-beta-candidate --include-smoke --scenario happy --json",
    "zeus release-gated-ulw --target-version v1.0.0-rc --json",
    "run full local regression and independent security review before stable release",
)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "token=",
    "private_key",
    "private-key",
    "-----begin",
)


class LiveBetaCandidateContract(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveBetaCandidateDecision
    target_version: str
    objective_contract_id: str
    release_stage: Literal["live_beta_candidate"]
    profile: Literal["live_beta_candidate"]
    live_beta_candidate_ready: bool
    production_ready: bool = False
    smoke_included: bool
    smoke_decision: Optional[str] = None
    surface_count: int
    live_beta_count: int
    blocked_count: int
    approval_required: bool
    required_controls: tuple[str, ...]
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    operator_note: Optional[str] = None
    raw_secret_marker_detected: bool = False
    live_cockpit: dict[str, JsonValue]
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    authority_widened: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> LiveBetaCandidateContract:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})


def build_live_beta_candidate_contract(
    *,
    include_smoke: bool = False,
    scenario: str = "happy",
    operator_note: Optional[str] = None,
) -> LiveBetaCandidateContract:
    parsed_scenario = parse_live_beta_candidate_scenario(scenario)
    safe_note = _safe_note(operator_note)
    secret_seen = _secret_seen(operator_note, safe_note)
    if secret_seen:
        return _blocked_contract(
            blocked_reasons=("raw_secret_marker_detected",),
            operator_note="[redacted-secret]",
            raw_secret_marker_detected=True,
        ).with_secret_scan()

    cockpit = LiveCockpitRuntime().build(include_smoke=include_smoke, scenario=parsed_scenario)
    blocked_reasons = tuple(cockpit.blocked_reasons)
    smoke_decision = None if cockpit.optin_smoke is None else cockpit.optin_smoke.decision
    decision: LiveBetaCandidateDecision = "blocked" if blocked_reasons else "report"
    ready = (
        decision == "report"
        and include_smoke
        and smoke_decision == "passed"
        and cockpit.live_beta_count >= 2
        and not cockpit.live_production_claimed
    )
    result = LiveBetaCandidateContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        release_stage="live_beta_candidate",
        profile="live_beta_candidate",
        live_beta_candidate_ready=ready,
        production_ready=False,
        smoke_included=include_smoke,
        smoke_decision=smoke_decision,
        surface_count=cockpit.surface_count,
        live_beta_count=cockpit.live_beta_count,
        blocked_count=cockpit.blocked_count,
        approval_required=cockpit.approval_required,
        required_controls=_REQUIRED_CONTROLS,
        blocked_reasons=blocked_reasons,
        recommended_next_commands=_RECOMMENDED_NEXT_COMMANDS,
        operator_note=safe_note,
        raw_secret_marker_detected=False,
        live_cockpit=cockpit.to_payload(),
        network_opened=cockpit.network_opened,
        handler_executed=cockpit.handler_executed,
        external_delivery_opened=cockpit.external_delivery_opened,
        credential_material_accessed=cockpit.credential_material_accessed,
        authority_widened=False,
        live_production_claimed=cockpit.live_production_claimed,
    )
    return result.with_secret_scan()


def parse_live_beta_candidate_scenario(scenario: str) -> LiveOptInSmokeScenario:
    if scenario == "happy":
        return "happy"
    if scenario == "blocked":
        return "blocked"
    raise ValueError(_SCENARIO_ERROR)


def _blocked_contract(
    *,
    blocked_reasons: tuple[str, ...],
    operator_note: Optional[str],
    raw_secret_marker_detected: bool,
) -> LiveBetaCandidateContract:
    return LiveBetaCandidateContract(
        decision="blocked",
        target_version=_TARGET_VERSION,
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        release_stage="live_beta_candidate",
        profile="live_beta_candidate",
        live_beta_candidate_ready=False,
        production_ready=False,
        smoke_included=False,
        smoke_decision=None,
        surface_count=0,
        live_beta_count=0,
        blocked_count=0,
        approval_required=True,
        required_controls=_REQUIRED_CONTROLS,
        blocked_reasons=blocked_reasons,
        recommended_next_commands=_RECOMMENDED_NEXT_COMMANDS,
        operator_note=operator_note,
        raw_secret_marker_detected=raw_secret_marker_detected,
        live_cockpit={},
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        authority_widened=False,
        live_production_claimed=False,
    )


def _safe_note(operator_note: Optional[str]) -> Optional[str]:
    if operator_note is None:
        return None
    return redact_secret_spans(operator_note)


def _secret_seen(operator_note: Optional[str], safe_note: Optional[str]) -> bool:
    if operator_note is None:
        return False
    return operator_note.strip() != safe_note
