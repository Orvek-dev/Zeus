from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.security import SecurityPlan, SecurityPlanBuilder, SecurityPlanningRequest

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_NOW: Final = datetime(2026, 6, 4, 11, 45, tzinfo=timezone.utc)
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


class SecurityCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: str
    control_count: int
    allowed_control_count: int
    blocked_control_count: int
    controls: tuple[dict[str, JsonValue], ...]
    selected_control: Optional[dict[str, JsonValue]] = None
    credential_readiness: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    authority_widened: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class SecurityCockpitRuntime:
    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = home

    def build(
        self,
        *,
        control_id: Optional[str] = None,
        include_credentials: bool = False,
    ) -> SecurityCockpitResult:
        controls = _control_summaries()
        selected = _find_selected_control(controls, control_id)
        blocked_reasons = _blocked_reasons(control_id=control_id, selected_control=selected)
        credential_readiness = self._credential_readiness_payload(include_credentials=include_credentials)
        result = SecurityCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            control_count=len(controls),
            allowed_control_count=sum(1 for item in controls if item["decision"] == "allowed"),
            blocked_control_count=sum(1 for item in controls if item["decision"] == "blocked"),
            controls=controls,
            selected_control=selected,
            credential_readiness=credential_readiness,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(control_id=control_id),
            authority_widened=False,
            credential_material_accessed=False,
            network_opened=any(bool(item["network_opened"]) for item in controls),
            handler_executed=any(bool(item["handler_executed"]) for item in controls),
            external_delivery_opened=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})

    def _credential_readiness_payload(
        self,
        *,
        include_credentials: bool,
    ) -> Optional[dict[str, JsonValue]]:
        if not include_credentials:
            return None
        if self.home is None:
            return None
        return CredentialReadinessRuntime(self.home).build().to_payload()


def _control_summaries() -> tuple[dict[str, JsonValue], ...]:
    builder = SecurityPlanBuilder()
    provider_lease = _provider_lease()
    return (
        _summary(
            control_id="local-safe",
            plan=builder.build(
                SecurityPlanningRequest(
                    surface_kind="local",
                    capability_id="local.status",
                    dry_run=True,
                    evidence_target="mneme.wave49.security.local",
                ),
            ),
            approval_required=False,
        ),
        _summary(
            control_id="lease-scope",
            plan=builder.build(
                SecurityPlanningRequest(
                    surface_kind="provider",
                    capability_id="provider.external.generate",
                    requested_scope="external.openai.readonly",
                    network_host="api.openai.com",
                    dry_run=True,
                    evidence_target="mneme.wave49.security.provider",
                ),
                runtime_lease=provider_lease,
            ),
            approval_required=False,
        ),
        _summary(
            control_id="missing-lease",
            plan=builder.build(
                SecurityPlanningRequest(
                    surface_kind="gateway",
                    capability_id="gateway.dispatch.plan",
                    network_host="gateway.local",
                    dry_run=True,
                    evidence_target="mneme.wave49.security.gateway",
                ),
            ),
            approval_required=True,
        ),
        _summary(
            control_id="secret-echo",
            plan=builder.build(
                SecurityPlanningRequest(
                    surface_kind="provider",
                    capability_id="provider.external.generate",
                    requested_scope="sk-" + "wave49-secret",
                    dry_run=True,
                    evidence_target="mneme.wave49.security.provider",
                ),
                runtime_lease=provider_lease,
            ),
            approval_required=True,
        ),
    )


def _summary(
    *,
    control_id: str,
    plan: SecurityPlan,
    approval_required: bool,
) -> dict[str, JsonValue]:
    return {
        "control_id": control_id,
        "decision": plan.decision,
        "reason": plan.reason,
        "surface_kind": plan.surface_kind,
        "capability_id": plan.capability_id,
        "dry_run": plan.dry_run,
        "scope_matched": plan.scope_matched,
        "redacted_input": plan.redacted_input,
        "approval_required": approval_required,
        "authority_widened": False,
        "network_opened": plan.network_opened,
        "handler_executed": plan.handler_executed,
        "external_delivery_opened": False,
        "live_production_claimed": False,
    }


def _provider_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave49.lease.security",
        objective_id="wave49.objective.security",
        principal_id="wave49.principal.operator",
        run_id="wave49.run.security",
        allowed_capabilities=("provider.external.generate",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.com",),
        budget_limit=100,
        evidence_target="mneme.wave49.security.provider",
        live_transport_allowed=False,
        issued_at=_NOW,
        expires_at=datetime(2026, 6, 5, 11, 45, tzinfo=timezone.utc),
    )


def _find_selected_control(
    controls: tuple[dict[str, JsonValue], ...],
    control_id: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if control_id is None:
        return None
    for control in controls:
        if control["control_id"] == control_id:
            return control
    return None


def _blocked_reasons(
    *,
    control_id: Optional[str],
    selected_control: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if control_id is not None and selected_control is None:
        return ("unknown_security_control",)
    return ()


def _recommended_next_commands(*, control_id: Optional[str]) -> tuple[str, ...]:
    if control_id is None:
        return (
            "zeus security --control-id lease-scope --json",
            "zeus security --control-id secret-echo --json",
            "zeus live --json",
        )
    return (
        "zeus live --json",
        "zeus runtime --json",
        "zeus workflow --json",
    )


def _no_secret_echo(result: SecurityCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
