from __future__ import annotations

import json
from typing import Final, Optional

from zeus_agent.approval_receipt_runtime import ApprovalReceiptResult
from zeus_agent.live_dry_run_runtime.models import LiveDryRunDecision, LiveDryRunResult
from zeus_agent.live_execute_runtime import LiveExecutePlanResult
from zeus_agent.live_handoff_runtime import LiveHandoffResult
from zeus_agent.live_preflight_runtime import LivePreflightResult
from zeus_agent.live_profile_runtime import LiveProfileResult

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


def build_dry_run_result(
    *,
    surface_id: str,
    profile: LiveProfileResult,
    blocked_reasons: tuple[str, ...],
    approval_receipt: Optional[ApprovalReceiptResult] = None,
    preflight: Optional[LivePreflightResult] = None,
    handoff: Optional[LiveHandoffResult] = None,
    execute_plan: Optional[LiveExecutePlanResult] = None,
    decision: Optional[LiveDryRunDecision] = None,
) -> LiveDryRunResult:
    final_decision: LiveDryRunDecision = decision or ("blocked" if blocked_reasons else "planned")
    result = LiveDryRunResult(
        decision=final_decision,
        surface_id=surface_id,
        profile=profile,
        approval_receipt=approval_receipt,
        preflight=preflight,
        handoff=handoff,
        execute_plan=execute_plan,
        blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
        execution_allowed=False,
        authority_granted=False,
        live_transport_enabled=False,
        network_opened=_network_opened(preflight, handoff, execute_plan),
        handler_executed=_handler_executed(preflight, handoff, execute_plan),
        external_delivery_opened=_external_delivery_opened(preflight, handoff, execute_plan),
        credential_material_accessed=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _network_opened(
    preflight: Optional[LivePreflightResult],
    handoff: Optional[LiveHandoffResult],
    execute_plan: Optional[LiveExecutePlanResult],
) -> bool:
    return bool(
        (preflight.network_opened if preflight is not None else False)
        or (handoff.network_opened if handoff is not None else False)
        or (execute_plan.network_opened if execute_plan is not None else False)
    )


def _handler_executed(
    preflight: Optional[LivePreflightResult],
    handoff: Optional[LiveHandoffResult],
    execute_plan: Optional[LiveExecutePlanResult],
) -> bool:
    return bool(
        (preflight.handler_executed if preflight is not None else False)
        or (handoff.handler_executed if handoff is not None else False)
        or (execute_plan.handler_executed if execute_plan is not None else False)
    )


def _external_delivery_opened(
    preflight: Optional[LivePreflightResult],
    handoff: Optional[LiveHandoffResult],
    execute_plan: Optional[LiveExecutePlanResult],
) -> bool:
    return bool(
        (preflight.external_delivery_opened if preflight is not None else False)
        or (handoff.external_delivery_opened if handoff is not None else False)
        or (execute_plan.external_delivery_opened if execute_plan is not None else False)
    )


def _no_secret_echo(result: LiveDryRunResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
