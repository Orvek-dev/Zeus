from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from zeus_agent.kernel.authority import (
    ApprovalReceipt,
    AuthorityContext,
    CapabilityGrant,
    CredentialGrant,
    NetworkGrant,
)

from .models import LiveCapability
from .registry import default_live_capability_registry

_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class TrustedLiveGovernanceRecord(BaseModel):
    model_config = _MODEL_CONFIG

    capability_id: str
    lease_ref: str
    approval_ref: str
    promotion_guard_ref: str
    broker_evidence_ref: str
    authority: AuthorityContext
    approval: ApprovalReceipt

    @field_validator(
        "capability_id",
        "lease_ref",
        "approval_ref",
        "promotion_guard_ref",
        "broker_evidence_ref",
    )
    @classmethod
    def _validate_required_text(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)


class LiveGovernanceTrustStore:
    def __init__(self, records: tuple[TrustedLiveGovernanceRecord, ...] = ()) -> None:
        self._records = records

    def resolve(
        self,
        *,
        capability_id: str,
        lease_ref: str,
        approval_ref: str,
        promotion_guard_ref: str,
        broker_evidence_ref: str,
    ) -> Optional[TrustedLiveGovernanceRecord]:
        for record in self._records:
            if (
                record.capability_id == capability_id
                and record.lease_ref == lease_ref
                and record.approval_ref == approval_ref
                and record.promotion_guard_ref == promotion_guard_ref
                and record.broker_evidence_ref == broker_evidence_ref
            ):
                return record
        return None


def trusted_record_for_capability(capability: LiveCapability) -> TrustedLiveGovernanceRecord:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    authority = AuthorityContext(
        principal_id="zeus.v210.governed_live",
        run_id="zeus.v210.governed_live.run",
        goal_contract_id="zeus.v210.kernel_throughput",
        capability_grants=[
            CapabilityGrant(capability_id=capability.capability_id, expires_at=expires_at),
        ],
        credential_grants=[
            CredentialGrant(
                capability_id=capability.capability_id,
                credential_scope=capability.credential_scope,
            ),
        ],
        network_grants=[
            NetworkGrant(
                capability_id=capability.capability_id,
                network_host=network_host,
            )
            for network_host in capability.network_hosts
        ],
    )
    approval = ApprovalReceipt(
        principal_id=authority.principal_id,
        run_id=authority.run_id,
        goal_contract_id=authority.goal_contract_id,
        approved_capabilities=[capability.capability_id],
        request_fingerprint=capability.approval_ref,
        nonce="v210-governed-live",
    )
    return TrustedLiveGovernanceRecord(
        capability_id=capability.capability_id,
        lease_ref=capability.lease_ref,
        approval_ref=capability.approval_ref,
        promotion_guard_ref=capability.promotion_guard_ref,
        broker_evidence_ref=capability.broker_evidence_ref,
        authority=authority,
        approval=approval,
    )


def default_live_governance_trust_store() -> LiveGovernanceTrustStore:
    registry = default_live_capability_registry()
    return LiveGovernanceTrustStore(
        tuple(trusted_record_for_capability(capability) for capability in registry.list_capabilities()),
    )
