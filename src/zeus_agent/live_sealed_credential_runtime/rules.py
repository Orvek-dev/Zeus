from __future__ import annotations

import re
from typing import Final, Optional

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_sealed_credential_runtime.models import LiveSealedCredentialReceipt
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult
from zeus_agent.security.credentials import redact_secret_spans

ENV_REF_PREFIX: Final = "env://"
ENV_NAME_PATTERN: Final = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def injection_reasons(injection: Optional[LiveCredentialInjectionResult]) -> tuple[str, ...]:
    if injection is None:
        return ("credential_injection_required",)
    reasons = []
    if injection.decision != "injection_ready" or not injection.credential_injection_ready:
        reasons.append("credential_injection_not_ready")
    if injection.material_proof_id is None or injection.header_name is None or injection.header_value_ref is None:
        reasons.append("credential_injection_header_missing")
    if injection.credential_material_accessed or injection.material_released or injection.raw_secret_returned:
        reasons.append("credential_injection_secret_boundary_failed")
    if not injection.no_secret_echo:
        reasons.append("credential_injection_secret_boundary_failed")
    if injection.network_opened or injection.external_delivery_opened or injection.live_transport_enabled:
        reasons.append("credential_injection_side_effect_detected")
    if injection.execution_allowed or injection.live_production_claimed:
        reasons.append("credential_injection_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def secret_material_reasons(secret_material: Optional[LiveSecretMaterialResult]) -> tuple[str, ...]:
    if secret_material is None:
        return ("secret_material_required",)
    reasons = []
    if secret_material.decision != "available" or not secret_material.material_available:
        reasons.append("secret_material_not_available")
    if secret_material.material_proof_id is None:
        reasons.append("secret_material_proof_required")
    if secret_material.material_released or secret_material.raw_secret_returned:
        reasons.append("secret_material_leak_detected")
    if secret_material.network_opened or secret_material.external_delivery_opened or secret_material.live_transport_enabled:
        reasons.append("secret_material_side_effect_detected")
    if secret_material.live_production_claimed or not secret_material.no_secret_echo:
        reasons.append("secret_material_secret_boundary_failed")
    if env_name(secret_material.secret_ref) is None:
        reasons.append("unsupported_secret_ref")
    return tuple(dict.fromkeys(reasons))


def binding_reasons(
    injection: Optional[LiveCredentialInjectionResult],
    secret_material: Optional[LiveSecretMaterialResult],
) -> tuple[str, ...]:
    if injection is None or secret_material is None:
        return ()
    expected_ref = None
    if secret_material.material_proof_id is not None:
        expected_ref = "secret-proof://{0}".format(secret_material.material_proof_id)
    if injection.material_proof_id != secret_material.material_proof_id:
        return ("credential_injection_material_mismatch",)
    if injection.secret_ref != secret_material.secret_ref:
        return ("credential_injection_material_mismatch",)
    if expected_ref is None or injection.header_value_ref != expected_ref:
        return ("credential_injection_material_mismatch",)
    return ()


def receipt_reasons(receipt: LiveSealedCredentialReceipt, injection: LiveCredentialInjectionResult) -> tuple[str, ...]:
    reasons = []
    if not receipt.credential_value_received:
        reasons.append("sealed_credential_not_received")
    if receipt.header_name_seen != injection.header_name or receipt.header_value_ref_seen != injection.header_value_ref:
        reasons.append("sealed_credential_header_mismatch")
    if receipt.material_released or receipt.raw_secret_returned or not receipt.no_secret_echo:
        reasons.append("sealed_credential_receipt_secret_boundary_failed")
    if _safe_optional(receipt.consumer_ref) is None:
        reasons.append("consumer_ref_required")
    return tuple(dict.fromkeys(reasons))


def env_name(secret_ref: str) -> Optional[str]:
    if not secret_ref.startswith(ENV_REF_PREFIX):
        return None
    value = secret_ref[len(ENV_REF_PREFIX) :].strip()
    if ENV_NAME_PATTERN.fullmatch(value) is None:
        return None
    return value


def header_value(header_name: str, material: str) -> Optional[str]:
    if header_name == "Authorization":
        return "Bearer {0}".format(material)
    if header_name == "X-API-Key":
        return material
    return None


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted
