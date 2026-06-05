from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseResult
from zeus_agent.security.credentials import redact_secret_spans

LiveSecretMaterialDecision = Literal["available", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_ENV_REF_PREFIX: Final = "env://"
_ENV_NAME_PATTERN: Final = re.compile(r"^[A-Z_][A-Z0-9_]*$")
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


class LiveSecretMaterialResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveSecretMaterialDecision
    material_proof_id: Optional[str]
    secret_ref: str
    secret_source: Optional[Literal["env"]] = None
    material_available: bool = False
    blocked_reasons: tuple[str, ...] = ()
    env_value_read: bool = False
    vault_value_read: bool = False
    credential_material_accessed: bool = False
    material_released: bool = False
    raw_secret_returned: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveSecretMaterialRuntime:
    def check(
        self,
        *,
        transport_lease: Optional[LiveTransportLeaseResult],
        secret_ref: str,
        allow_material_access: bool = False,
    ) -> LiveSecretMaterialResult:
        safe_ref = redact_secret_spans(secret_ref.strip())
        reasons = list(_transport_reasons(transport_lease))
        if safe_ref != secret_ref.strip():
            reasons.append("unsafe_secret_ref")
        env_name = _env_name(safe_ref)
        if env_name is None:
            reasons.append("unsupported_secret_ref")
        if not allow_material_access:
            reasons.append("secret_material_access_not_approved")
        if reasons:
            return _result(
                decision="blocked",
                secret_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )

        material = os.environ.get(env_name or "")
        accessed = True
        if material is None or material == "":
            return _result(
                decision="blocked",
                secret_ref=safe_ref,
                secret_source="env",
                blocked_reasons=("secret_material_missing",),
                env_value_read=True,
                credential_material_accessed=accessed,
            )
        return _result(
            decision="available",
            secret_ref=safe_ref,
            secret_source="env",
            material_proof_id=_material_proof_id(
                transport_lease=transport_lease,
                secret_ref=safe_ref,
            ),
            material_available=True,
            env_value_read=True,
            credential_material_accessed=accessed,
        )


def _transport_reasons(transport_lease: Optional[LiveTransportLeaseResult]) -> tuple[str, ...]:
    if transport_lease is None:
        return ("transport_lease_required",)
    reasons = []
    if transport_lease.decision != "bound" or not transport_lease.transport_lease_bound:
        reasons.append("transport_lease_not_bound")
    if not transport_lease.lease_authorized:
        reasons.append("transport_lease_not_authorized")
    if transport_lease.live_transport_enabled or transport_lease.network_opened:
        reasons.append("transport_lease_side_effect_detected")
    if transport_lease.handler_executed or transport_lease.external_delivery_opened:
        reasons.append("transport_lease_side_effect_detected")
    if transport_lease.credential_material_accessed or transport_lease.live_production_claimed:
        reasons.append("transport_lease_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _env_name(secret_ref: str) -> Optional[str]:
    if not secret_ref.startswith(_ENV_REF_PREFIX):
        return None
    env_name = secret_ref[len(_ENV_REF_PREFIX) :].strip()
    if _ENV_NAME_PATTERN.fullmatch(env_name) is None:
        return None
    return env_name


def _material_proof_id(
    *,
    transport_lease: Optional[LiveTransportLeaseResult],
    secret_ref: str,
) -> str:
    payload = {
        "secret_ref": secret_ref,
        "transport_lease_id": None if transport_lease is None else transport_lease.transport_lease_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-secret-material-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveSecretMaterialDecision,
    secret_ref: str,
    material_proof_id: Optional[str] = None,
    secret_source: Optional[Literal["env"]] = None,
    material_available: bool = False,
    blocked_reasons: tuple[str, ...] = (),
    env_value_read: bool = False,
    credential_material_accessed: bool = False,
) -> LiveSecretMaterialResult:
    result = LiveSecretMaterialResult(
        decision=decision,
        material_proof_id=material_proof_id,
        secret_ref=secret_ref,
        secret_source=secret_source,
        material_available=material_available,
        blocked_reasons=blocked_reasons,
        env_value_read=env_value_read,
        vault_value_read=False,
        credential_material_accessed=credential_material_accessed,
        material_released=False,
        raw_secret_returned=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        execution_allowed=False,
        authority_granted=False,
        live_transport_enabled=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _no_secret_echo(result: LiveSecretMaterialResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
