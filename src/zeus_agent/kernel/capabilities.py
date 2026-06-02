from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .authority import ApprovalReceipt, AuthorityContext


def _require_non_empty(value: str, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("{0} must be non-empty".format(field_name))
    return text


class CapabilityRisk(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class CapabilityHealth(str, Enum):
    healthy = "healthy"
    unhealthy = "unhealthy"


class SideEffect(str, Enum):
    none = "none"
    local_process = "local_process"
    network = "network"
    filesystem_write = "filesystem_write"


class EvidenceObligation(str, Enum):
    none = "none"
    decision = "decision"
    artifact = "artifact"


class CapabilityDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    name: str
    risk: CapabilityRisk
    input_schema: Dict[str, object]
    output_schema: Dict[str, object]
    description: Optional[str] = None
    health: CapabilityHealth = CapabilityHealth.healthy
    side_effects: List[SideEffect] = Field(default_factory=list)
    evidence_obligation: EvidenceObligation = EvidenceObligation.decision
    profiles: List[str] = Field(default_factory=lambda: ["*"])

    @field_validator("capability_id", "name")
    @classmethod
    def _validate_non_empty_required(cls, value: str, info: object) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _require_non_empty(value, "description")

    @field_validator("profiles")
    @classmethod
    def _validate_profiles(cls, values: List[str]) -> List[str]:
        if not values:
            raise ValueError("profiles must be non-empty")
        return [_require_non_empty(value, "profiles") for value in values]


class CapabilityGraph:
    def __init__(self, descriptors: Sequence[CapabilityDescriptor]):
        self._descriptors = list(descriptors)
        seen_capability_ids = set()
        seen_names = set()
        for descriptor in self._descriptors:
            if descriptor.capability_id in seen_capability_ids:
                raise ValueError(
                    "duplicate capability_id: {0}".format(descriptor.capability_id)
                )
            if descriptor.name in seen_names:
                raise ValueError("duplicate name: {0}".format(descriptor.name))
            seen_capability_ids.add(descriptor.capability_id)
            seen_names.add(descriptor.name)

    def compile_model_schema(
        self,
        profile: str,
        authority: AuthorityContext,
        approval_receipts: Optional[Sequence[ApprovalReceipt]] = None,
        include_unhealthy: bool = False,
    ) -> List[Dict[str, object]]:
        profile_value = _require_non_empty(profile, "profile")
        approved_capabilities = self._collect_approved_capabilities(
            authority=authority,
            approval_receipts=approval_receipts or [],
        )

        result = []
        for descriptor in self._descriptors:
            if not self._profile_matches(descriptor, profile_value):
                continue
            if not include_unhealthy and descriptor.health != CapabilityHealth.healthy:
                continue
            if authority.allows(descriptor.capability_id).decision != "allowed":
                continue
            if self._needs_approval(descriptor) and descriptor.capability_id not in approved_capabilities:
                continue

            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": descriptor.name,
                        "description": descriptor.description or descriptor.name,
                        "parameters": descriptor.input_schema,
                    },
                }
            )

        return result

    def descriptor_for(self, capability_id: str) -> Optional[CapabilityDescriptor]:
        for descriptor in self._descriptors:
            if descriptor.capability_id == capability_id:
                return descriptor
        return None

    @staticmethod
    def _profile_matches(descriptor: CapabilityDescriptor, profile: str) -> bool:
        return "*" in descriptor.profiles or profile in descriptor.profiles

    @staticmethod
    def _needs_approval(descriptor: CapabilityDescriptor) -> bool:
        return descriptor.risk == CapabilityRisk.high or len(descriptor.side_effects) > 0

    @staticmethod
    def _collect_approved_capabilities(
        authority: AuthorityContext,
        approval_receipts: Sequence[ApprovalReceipt],
    ) -> set:
        approved = set()
        for receipt in approval_receipts:
            try:
                receipt.assert_within_authority(authority)
            except ValueError:
                continue
            approved.update(receipt.approved_capabilities)
        return approved
