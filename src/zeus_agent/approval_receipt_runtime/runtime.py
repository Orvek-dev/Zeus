from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue, field_validator

from zeus_agent.approval_cockpit_runtime import ApprovalCockpitRuntime
from zeus_agent.security.credentials import redact_secret_spans

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_DEFAULT_NOW: Final = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
_DEFAULT_TTL_MINUTES: Final = 30
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


class ApprovalReceiptResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["recorded", "blocked"]
    approval_id: str
    principal_id: str
    objective_id: str
    capability_id: str
    receipt_id: Optional[str] = None
    proof_hash: Optional[str] = None
    issued_at: str
    expires_at: str
    ttl_minutes: int
    selected_gate: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    approval_receipt_recorded: bool
    authority_granted: bool = False
    live_transport_enabled: bool = False
    human_prompt_required: bool = True
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    recommended_next_commands: tuple[str, ...] = ()

    @field_validator("ttl_minutes")
    def _ttl_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("approval_receipt_ttl_must_be_positive")
        return value

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class ApprovalReceiptRuntime:
    def record(
        self,
        *,
        approval_id: str,
        principal_id: str,
        objective_id: str,
        capability_id: str,
        now: Optional[datetime] = None,
        ttl_minutes: int = _DEFAULT_TTL_MINUTES,
    ) -> ApprovalReceiptResult:
        issued_at = _normalized_now(now)
        expires_at = issued_at + timedelta(minutes=ttl_minutes)
        safe_approval_id, approval_secret = _safe_field(approval_id)
        safe_principal_id, principal_secret = _safe_field(principal_id)
        safe_objective_id, objective_secret = _safe_field(objective_id)
        safe_capability_id, capability_secret = _safe_field(capability_id)

        cockpit = ApprovalCockpitRuntime().build(approval_id=safe_approval_id)
        selected_gate = cockpit.selected_gate
        reasons = list(cockpit.blocked_reasons)
        if selected_gate is not None and selected_gate["required_scope"] != safe_capability_id:
            reasons.append("capability_scope_mismatch")
        if approval_secret or principal_secret or objective_secret or capability_secret:
            reasons.append("secret_like_receipt_field")

        decision: Literal["recorded", "blocked"] = "blocked" if reasons else "recorded"
        receipt_recorded = decision == "recorded"
        proof_payload = _proof_payload(
            approval_id=safe_approval_id,
            principal_id=safe_principal_id,
            objective_id=safe_objective_id,
            capability_id=safe_capability_id,
            issued_at=issued_at.isoformat(),
            expires_at=expires_at.isoformat(),
            ttl_minutes=ttl_minutes,
        )
        proof_hash = _proof_hash(proof_payload)
        result = ApprovalReceiptResult(
            decision=decision,
            approval_id=safe_approval_id,
            principal_id=safe_principal_id,
            objective_id=safe_objective_id,
            capability_id=safe_capability_id,
            receipt_id="approval-receipt-{0}".format(proof_hash.removeprefix("sha256:")[:16])
            if receipt_recorded
            else None,
            proof_hash=proof_hash if receipt_recorded else None,
            issued_at=issued_at.isoformat(),
            expires_at=expires_at.isoformat(),
            ttl_minutes=ttl_minutes,
            selected_gate=selected_gate,
            blocked_reasons=tuple(dict.fromkeys(reasons)),
            approval_receipt_recorded=receipt_recorded,
            authority_granted=False,
            live_transport_enabled=False,
            credential_material_accessed=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            live_production_claimed=False,
            recommended_next_commands=_recommended_next_commands(
                decision=decision,
                approval_id=safe_approval_id,
            ),
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _normalized_now(now: Optional[datetime]) -> datetime:
    if now is None:
        return _DEFAULT_NOW
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _safe_field(value: str) -> tuple[str, bool]:
    redacted = redact_secret_spans(value)
    return redacted, redacted != value.strip()


def _proof_payload(
    *,
    approval_id: str,
    principal_id: str,
    objective_id: str,
    capability_id: str,
    issued_at: str,
    expires_at: str,
    ttl_minutes: int,
) -> dict[str, JsonValue]:
    return {
        "approval_id": approval_id,
        "principal_id": principal_id,
        "objective_id": objective_id,
        "capability_id": capability_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "ttl_minutes": ttl_minutes,
        "authority_granted": False,
        "live_transport_enabled": False,
        "live_production_claimed": False,
    }


def _proof_hash(payload: dict[str, JsonValue]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:{0}".format(hashlib.sha256(encoded).hexdigest())


def _recommended_next_commands(
    *,
    decision: Literal["recorded", "blocked"],
    approval_id: str,
) -> tuple[str, ...]:
    if decision == "recorded":
        return (
            "zeus live --json",
            "zeus security --control-id lease-scope --json",
            "zeus live-optin-smoke --scenario happy --json",
        )
    return (
        "zeus approvals --approval-id {0} --json".format(approval_id),
        "zeus security --json",
        "zeus live --json",
    )


def _no_secret_echo(result: ApprovalReceiptResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
