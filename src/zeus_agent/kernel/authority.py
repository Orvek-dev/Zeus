from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Literal, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _require_non_empty(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("{0} must be non-empty".format(field_name))
    return text


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class AuthorityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["allowed", "blocked"]
    reason: str
    capability_id: Optional[str] = None

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        return _require_non_empty(value, "reason")

    @field_validator("capability_id")
    @classmethod
    def _validate_capability_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, "capability_id")


class CapabilityGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    expires_at: Optional[datetime] = None

    @field_validator("capability_id")
    @classmethod
    def _validate_capability_id(cls, value: str) -> str:
        return _require_non_empty(value, "capability_id")


class PathGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    path_prefix: str

    @field_validator("capability_id", "path_prefix")
    @classmethod
    def _validate_fields(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)


class NetworkGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    network_host: str

    @field_validator("capability_id", "network_host")
    @classmethod
    def _validate_fields(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)


class CredentialGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    credential_scope: str

    @field_validator("capability_id", "credential_scope")
    @classmethod
    def _validate_fields(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)


class AuthorityContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal_id: str
    run_id: str
    goal_contract_id: str
    capability_grants: List[CapabilityGrant]
    path_grants: List[PathGrant] = Field(default_factory=list)
    network_grants: List[NetworkGrant] = Field(default_factory=list)
    credential_grants: List[CredentialGrant] = Field(default_factory=list)

    @field_validator("principal_id", "run_id", "goal_contract_id")
    @classmethod
    def _validate_ids(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)

    def allows(
        self,
        capability_id: str,
        *,
        path: Optional[str] = None,
        network_host: Optional[str] = None,
        credential_scope: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> AuthorityDecision:
        capability = capability_id.strip()
        if not capability:
            return AuthorityDecision(decision="blocked", reason="invalid_capability_id")

        timestamp = _to_utc(now) if now is not None else datetime.now(timezone.utc)
        grants = [grant for grant in self.capability_grants if grant.capability_id == capability]
        if not grants:
            return AuthorityDecision(
                decision="blocked",
                reason="capability_not_granted",
                capability_id=capability,
            )

        valid_grants = []
        for grant in grants:
            if grant.expires_at is None or _to_utc(grant.expires_at) >= timestamp:
                valid_grants.append(grant)
        if not valid_grants:
            return AuthorityDecision(
                decision="blocked",
                reason="capability_grant_expired",
                capability_id=capability,
            )

        if path is not None:
            path_rules = [rule for rule in self.path_grants if rule.capability_id == capability]
            if not path_rules:
                return AuthorityDecision(
                    decision="blocked",
                    reason="path_scope_missing",
                    capability_id=capability,
                )
            if not any(path.startswith(rule.path_prefix) for rule in path_rules):
                return AuthorityDecision(
                    decision="blocked",
                    reason="path_scope_blocked",
                    capability_id=capability,
                )

        if network_host is not None:
            network_rules = [rule for rule in self.network_grants if rule.capability_id == capability]
            if not network_rules:
                return AuthorityDecision(
                    decision="blocked",
                    reason="network_scope_missing",
                    capability_id=capability,
                )
            if network_host not in {rule.network_host for rule in network_rules}:
                return AuthorityDecision(
                    decision="blocked",
                    reason="network_scope_blocked",
                    capability_id=capability,
                )

        if credential_scope is not None:
            credential_rules = [
                rule for rule in self.credential_grants if rule.capability_id == capability
            ]
            if not credential_rules:
                return AuthorityDecision(
                    decision="blocked",
                    reason="credential_scope_missing",
                    capability_id=capability,
                )
            if credential_scope not in {rule.credential_scope for rule in credential_rules}:
                return AuthorityDecision(
                    decision="blocked",
                    reason="credential_scope_blocked",
                    capability_id=capability,
                )

        return AuthorityDecision(
            decision="allowed",
            reason="capability_granted",
            capability_id=capability,
        )

    def derive_for_child(
        self,
        child_principal_id: str,
        requested_capabilities: Sequence[str],
    ) -> "AuthorityContext":
        requested = {_require_non_empty(item, "requested_capabilities") for item in requested_capabilities}
        invalid = [capability for capability in requested if self.allows(capability).decision != "allowed"]
        if invalid:
            raise ValueError("requested capability outside parent scope: {0}".format(", ".join(sorted(invalid))))

        child_capability_grants = [
            grant for grant in self.capability_grants if grant.capability_id in requested
        ]
        child_path_grants = [grant for grant in self.path_grants if grant.capability_id in requested]
        child_network_grants = [
            grant for grant in self.network_grants if grant.capability_id in requested
        ]
        child_credential_grants = [
            grant for grant in self.credential_grants if grant.capability_id in requested
        ]

        return AuthorityContext(
            principal_id=_require_non_empty(child_principal_id, "child_principal_id"),
            run_id=self.run_id,
            goal_contract_id=self.goal_contract_id,
            capability_grants=child_capability_grants,
            path_grants=child_path_grants,
            network_grants=child_network_grants,
            credential_grants=child_credential_grants,
        )


class ApprovalReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal_id: str
    run_id: str
    goal_contract_id: str
    approved_capabilities: List[str]

    @field_validator("principal_id", "run_id", "goal_contract_id")
    @classmethod
    def _validate_ids(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("approved_capabilities")
    @classmethod
    def _validate_approved_capabilities(cls, values: List[str]) -> List[str]:
        return [_require_non_empty(value, "approved_capabilities") for value in values]

    def assert_within_authority(self, authority: AuthorityContext) -> None:
        if authority.run_id != self.run_id:
            raise ValueError("approval run_id mismatch")
        if authority.goal_contract_id != self.goal_contract_id:
            raise ValueError("approval goal_contract_id mismatch")
        if authority.principal_id != self.principal_id:
            raise ValueError("approval principal_id mismatch")
        for capability in self.approved_capabilities:
            decision = authority.allows(capability)
            if decision.decision != "allowed":
                raise ValueError(
                    "approved capability outside authority scope: {0}".format(capability)
                )
