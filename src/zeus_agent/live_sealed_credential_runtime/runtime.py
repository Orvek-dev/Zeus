from __future__ import annotations

import hashlib
import json
import os
from typing import Optional

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_mcp_external_transport_runtime.response import no_secret_echo
from zeus_agent.live_sealed_credential_runtime.models import (
    LiveSealedCredential,
    LiveSealedCredentialConsumer,
    LiveSealedCredentialDecision,
    LiveSealedCredentialReceipt,
    LiveSealedCredentialReleaseResult,
)
from zeus_agent.live_sealed_credential_runtime.rules import (
    binding_reasons,
    env_name,
    header_value,
    injection_reasons,
    receipt_reasons,
    secret_material_reasons,
)
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult
from zeus_agent.security.credentials import redact_secret_spans


class LiveSealedCredentialRuntime:
    def release(
        self,
        *,
        injection: Optional[LiveCredentialInjectionResult],
        secret_material: Optional[LiveSecretMaterialResult],
        consumer: LiveSealedCredentialConsumer,
        release_ref: str,
    ) -> LiveSealedCredentialReleaseResult:
        safe_ref = _safe_optional(release_ref)
        reasons = list(injection_reasons(injection))
        reasons.extend(secret_material_reasons(secret_material))
        reasons.extend(binding_reasons(injection, secret_material))
        if safe_ref is None:
            reasons.append("release_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                injection=injection,
                secret_material=secret_material,
                release_ref=safe_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        material, material_reasons = _material(secret_material)
        if material_reasons:
            return _result(
                decision="blocked",
                injection=injection,
                secret_material=secret_material,
                release_ref=safe_ref,
                blocked_reasons=material_reasons,
                credential_material_accessed=True,
            )
        header = header_value(injection.header_name or "", material or "")
        if header is None:
            return _result(
                decision="blocked",
                injection=injection,
                secret_material=secret_material,
                release_ref=safe_ref,
                blocked_reasons=("unsupported_credential_header",),
                credential_material_accessed=True,
            )
        receipt = consumer.consume(
            LiveSealedCredential(
                header_name=injection.header_name or "",
                header_value_ref=injection.header_value_ref or "",
                _header_value=header,
            )
        )
        receipt_blockers = receipt_reasons(receipt, injection)
        if receipt_blockers:
            return _result(
                decision="blocked",
                injection=injection,
                secret_material=secret_material,
                release_ref=safe_ref,
                blocked_reasons=receipt_blockers,
                receipt=receipt,
                credential_material_accessed=True,
            )
        return _result(
            decision="released",
            injection=injection,
            secret_material=secret_material,
            release_ref=safe_ref,
            release_id=_release_id(injection, secret_material, receipt, safe_ref),
            receipt=receipt,
            credential_material_accessed=True,
            material_released_to_consumer=True,
            credential_injection_bound=True,
            secret_material_bound=True,
            consumer_bound=True,
            sealed_credential_released=True,
        )


def _safe_optional(value: str) -> Optional[str]:
    redacted = redact_secret_spans(value.strip())
    return None if redacted == "" else redacted


def _material(secret_material: Optional[LiveSecretMaterialResult]) -> tuple[Optional[str], tuple[str, ...]]:
    if secret_material is None:
        return None, ("secret_material_required",)
    name = env_name(secret_material.secret_ref)
    if name is None:
        return None, ("unsupported_secret_ref",)
    material = os.environ.get(name)
    if material is None or material == "":
        return None, ("secret_material_missing",)
    return material, ()


def _release_id(
    injection: Optional[LiveCredentialInjectionResult],
    secret_material: Optional[LiveSecretMaterialResult],
    receipt: LiveSealedCredentialReceipt,
    release_ref: Optional[str],
) -> str:
    payload = {
        "consumer_ref": receipt.consumer_ref,
        "injection_id": None if injection is None else injection.injection_id,
        "material_proof_id": None if secret_material is None else secret_material.material_proof_id,
        "release_ref": release_ref,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-sealed-credential-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveSealedCredentialDecision,
    injection: Optional[LiveCredentialInjectionResult],
    secret_material: Optional[LiveSecretMaterialResult],
    release_ref: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    release_id: Optional[str] = None,
    receipt: Optional[LiveSealedCredentialReceipt] = None,
    **flags: bool,
) -> LiveSealedCredentialReleaseResult:
    result = LiveSealedCredentialReleaseResult(
        decision=decision,
        release_id=release_id,
        injection_id=None if injection is None else injection.injection_id,
        material_proof_id=None if secret_material is None else secret_material.material_proof_id,
        consumer_ref=None if receipt is None else receipt.consumer_ref,
        release_ref=release_ref,
        header_name=None if injection is None else injection.header_name,
        header_value_ref=None if injection is None else injection.header_value_ref,
        blocked_reasons=blocked_reasons,
        **flags,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
