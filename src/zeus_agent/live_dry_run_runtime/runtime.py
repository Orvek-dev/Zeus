from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.approval_receipt_runtime import ApprovalReceiptResult, ApprovalReceiptRuntime
from zeus_agent.live_dry_run_runtime.models import LiveDryRunDecision, LiveDryRunResult
from zeus_agent.live_dry_run_runtime.result_builder import build_dry_run_result
from zeus_agent.live_execute_runtime import LiveExecutePlanRequest, LiveExecutePlanRuntime
from zeus_agent.live_handoff_runtime import LiveHandoffRequest, LiveHandoffRuntime
from zeus_agent.live_preflight_runtime import LivePreflightRequest, LivePreflightRuntime
from zeus_agent.live_profile_runtime import LiveProfileResult, LiveProfileRuntime
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.secret_resolver_runtime import SecretResolverPlanRuntime

_DEFAULT_NOW: Final = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)


class LiveDryRunRuntime:
    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = home

    def run(
        self,
        *,
        surface_id: str,
        principal_id: str,
        objective_id: str,
        delivery_target: Optional[str] = None,
        allowlisted_delivery_targets: tuple[str, ...] = (),
        execute_live: bool = False,
        check_credentials: bool = False,
        now: Optional[datetime] = None,
    ) -> LiveDryRunResult:
        timestamp = _normalized_now(now)
        profile = LiveProfileRuntime(home=self.home).build(
            surface_id=surface_id,
            principal_id=principal_id,
            objective_id=objective_id,
            delivery_target=delivery_target,
            allowlisted_delivery_targets=allowlisted_delivery_targets,
        )
        profile_reasons = _prefixed("profile", profile.blocked_reasons)
        if profile.decision == "blocked" or profile_reasons:
            return build_dry_run_result(
                surface_id=surface_id,
                profile=profile,
                blocked_reasons=profile_reasons,
            )

        receipt = ApprovalReceiptRuntime().record(
            approval_id=str(profile.approval_id),
            principal_id=principal_id,
            objective_id=objective_id,
            capability_id=str(profile.capability_id),
            now=timestamp,
        )
        receipt_reasons = _prefixed("approval_receipt", receipt.blocked_reasons)
        if receipt.decision == "blocked" or receipt_reasons:
            return build_dry_run_result(
                surface_id=surface_id,
                profile=profile,
                approval_receipt=receipt,
                blocked_reasons=receipt_reasons,
            )

        preflight_request = _preflight_request(profile, receipt)
        lease = _runtime_lease(profile, timestamp)
        preflight_home = self.home if check_credentials else None
        preflight = LivePreflightRuntime(home=preflight_home).evaluate(
            preflight_request,
            lease=lease,
            now=timestamp,
        )
        preflight_reasons = _prefixed("preflight", preflight.blocked_reasons)
        if preflight.decision == "blocked" or preflight_reasons:
            return build_dry_run_result(
                surface_id=surface_id,
                profile=profile,
                approval_receipt=receipt,
                preflight=preflight,
                blocked_reasons=preflight_reasons,
            )

        handoff = LiveHandoffRuntime().build(
            LiveHandoffRequest(
                handoff_id="{0}.handoff".format(objective_id),
                lease_id=str(profile.lease_template["lease_id"]),
                preflight=preflight,
            ),
        )
        handoff_reasons = _prefixed("handoff", handoff.blocked_reasons)
        if handoff.decision == "blocked" or handoff_reasons:
            return build_dry_run_result(
                surface_id=surface_id,
                profile=profile,
                approval_receipt=receipt,
                preflight=preflight,
                handoff=handoff,
                blocked_reasons=handoff_reasons,
            )

        secret_resolver_plan = _secret_resolver_plan(
            home=self.home,
            profile=profile,
            check_credentials=check_credentials,
        )
        execute_plan = LiveExecutePlanRuntime().plan(
            LiveExecutePlanRequest(
                execution_id="{0}.execute".format(objective_id),
                handoff=handoff,
                secret_resolver_plan=secret_resolver_plan,
                execute_live=execute_live,
            ),
        )
        execute_reasons = _prefixed("execute_plan", execute_plan.blocked_reasons)
        decision: LiveDryRunDecision = "blocked" if execute_reasons else "planned"
        return build_dry_run_result(
            surface_id=surface_id,
            profile=profile,
            approval_receipt=receipt,
            preflight=preflight,
            handoff=handoff,
            execute_plan=execute_plan,
            blocked_reasons=execute_reasons,
            decision=decision,
        )


def _normalized_now(now: Optional[datetime]) -> datetime:
    if now is None:
        return _DEFAULT_NOW
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _preflight_request(
    profile: LiveProfileResult,
    receipt: ApprovalReceiptResult,
) -> LivePreflightRequest:
    template = profile.preflight_request_template
    return LivePreflightRequest(
        preflight_id=str(template["preflight_id"]),
        approval_id=str(template["approval_id"]),
        principal_id=str(template["principal_id"]),
        objective_id=str(template["objective_id"]),
        surface_kind=str(template["surface_kind"]),
        surface_id=str(template["surface_id"]),
        capability_id=str(template["capability_id"]),
        evidence_target=str(template["evidence_target"]),
        credential_scope=_optional_str(template.get("credential_scope")),
        network_host=_optional_str(template.get("network_host")),
        approval_receipt_id=receipt.receipt_id,
        approval_proof_hash=receipt.proof_hash,
        probe_healthy=bool(template["probe_healthy"]),
        source_pinned=bool(template["source_pinned"]),
        mcp_description=_optional_str(template.get("mcp_description")),
        delivery_target=_optional_str(template.get("delivery_target")),
        allowlisted_delivery_targets=tuple(
            str(value) for value in template.get("allowlisted_delivery_targets", [])
        ),
        budget_required=int(template["budget_required"]),
        cleanup_required=bool(template["cleanup_required"]),
        live_production_claim_requested=bool(template["live_production_claim_requested"]),
    )


def _runtime_lease(profile: LiveProfileResult, now: datetime) -> RuntimeLease:
    template = profile.lease_template
    return RuntimeLease(
        lease_id=str(template["lease_id"]),
        objective_id=str(template["objective_id"]),
        principal_id=str(template["principal_id"]),
        run_id=str(template["run_id"]),
        allowed_capabilities=tuple(str(value) for value in template["allowed_capabilities"]),
        credential_scopes=tuple(str(value) for value in template["credential_scopes"]),
        network_hosts=tuple(str(value) for value in template["network_hosts"]),
        budget_limit=int(template["budget_limit"]),
        evidence_target=str(template["evidence_target"]),
        live_transport_allowed=bool(template["live_transport_allowed"]),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )


def _optional_str(value: object) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _prefixed(stage: str, reasons: tuple[str, ...]) -> tuple[str, ...]:
    return tuple("{0}:{1}".format(stage, reason) for reason in reasons)


def _secret_resolver_plan(
    *,
    home: Optional[Path],
    profile: LiveProfileResult,
    check_credentials: bool,
) -> Optional[dict[str, JsonValue]]:
    if not check_credentials or home is None:
        return None
    template = profile.preflight_request_template
    credential_scope = _optional_str(template.get("credential_scope"))
    if credential_scope is None:
        return None
    return SecretResolverPlanRuntime(home).plan(
        surface_kind=str(template["surface_kind"]),
        surface_id=str(template["surface_id"]),
        credential_scope=credential_scope,
        expected_endpoint=_secret_resolver_endpoint(template),
    ).to_payload()


def _secret_resolver_endpoint(template: dict[str, JsonValue]) -> Optional[str]:
    surface_kind = str(template["surface_kind"])
    if surface_kind == "gateway":
        return _optional_str(template.get("delivery_target"))
    if surface_kind == "provider":
        return _optional_str(template.get("network_host"))
    return None
