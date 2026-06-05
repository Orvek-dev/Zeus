from __future__ import annotations

import hashlib
import json
from typing import Final, Optional
from urllib.error import HTTPError, URLError

from pydantic import JsonValue

from zeus_agent.live_credential_injection_runtime import LiveCredentialInjectionResult
from zeus_agent.live_mcp_credentialed_http_runtime.http_client import mcp_endpoint_host, post_mcp_body
from zeus_agent.live_mcp_credentialed_http_runtime.models import (
    LiveMcpCredentialedHttpDecision,
    LiveMcpCredentialedHttpResult,
)
from zeus_agent.live_mcp_credentialed_http_runtime.rules import (
    binding_reasons,
    injection_reasons,
    mcp_envelope_reasons,
    request_body_reasons,
    safe_optional,
    transport_reasons,
)
from zeus_agent.live_mcp_credentialed_http_runtime.sealed_capture import CredentialCapture
from zeus_agent.live_mcp_external_transport_runtime.response import no_secret_echo
from zeus_agent.live_mcp_request_body_runtime import LiveMcpRequestBodyResult
from zeus_agent.live_mcp_request_runtime import LiveMcpRequestResult
from zeus_agent.live_sealed_credential_runtime import LiveSealedCredentialRuntime
from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult

_CLEANUP_RECEIPT: Final = "mcp-credentialed-http-client-closed"


class LiveMcpCredentialedHttpRuntime:
    def execute(
        self,
        *,
        injection: Optional[LiveCredentialInjectionResult],
        secret_material: Optional[LiveSecretMaterialResult],
        mcp_envelope: Optional[LiveMcpRequestResult],
        request_body: Optional[LiveMcpRequestBodyResult],
        transport_endpoint: str,
        timeout_ms: int,
        release_ref: str,
        execution_ref: str,
    ) -> LiveMcpCredentialedHttpResult:
        safe_endpoint = safe_optional(transport_endpoint)
        safe_release_ref = safe_optional(release_ref)
        safe_execution_ref = safe_optional(execution_ref)
        reasons = list(injection_reasons(injection))
        reasons.extend(mcp_envelope_reasons(mcp_envelope))
        reasons.extend(request_body_reasons(request_body))
        reasons.extend(binding_reasons(injection, mcp_envelope, request_body))
        reasons.extend(transport_reasons(safe_endpoint, timeout_ms))
        if safe_release_ref is None:
            reasons.append("release_ref_required")
        if safe_execution_ref is None:
            reasons.append("execution_ref_required")
        if reasons:
            return _result(
                decision="blocked",
                injection=injection,
                secret_material=secret_material,
                mcp_envelope=mcp_envelope,
                request_body=request_body,
                transport_endpoint=safe_endpoint,
                release_ref=safe_release_ref,
                execution_ref=safe_execution_ref,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
            )
        consumer = CredentialCapture("mcp-credentialed-http://consumer")
        release = LiveSealedCredentialRuntime().release(
            injection=injection,
            secret_material=secret_material,
            consumer=consumer,
            release_ref=safe_release_ref or "",
        )
        if release.decision != "released" or consumer.header_value is None:
            blockers = release.blocked_reasons or ("sealed_credential_release_blocked",)
            return _result(
                decision="blocked",
                injection=injection,
                secret_material=secret_material,
                mcp_envelope=mcp_envelope,
                request_body=request_body,
                transport_endpoint=safe_endpoint,
                release_ref=safe_release_ref,
                execution_ref=safe_execution_ref,
                release_id=release.release_id,
                blocked_reasons=tuple(dict.fromkeys(blockers)),
                credential_material_accessed=release.credential_material_accessed,
                material_released_to_consumer=release.material_released_to_consumer,
            )
        try:
            client_result = post_mcp_body(
                endpoint=safe_endpoint or "",
                header_name=consumer.header_name or "",
                header_value=consumer.header_value,
                body_payload=request_body.body_payload or {},
                timeout_ms=timeout_ms,
            )
        except HTTPError as exc:
            return _blocked_after_network(
                injection, secret_material, mcp_envelope, request_body, safe_endpoint,
                safe_release_ref, safe_execution_ref, release.release_id,
                "mcp_credentialed_http_status_error", exc.code,
            )
        except (TimeoutError, URLError):
            return _blocked_after_network(
                injection, secret_material, mcp_envelope, request_body, safe_endpoint,
                safe_release_ref, safe_execution_ref, release.release_id,
                "mcp_credentialed_http_transport_error", None,
            )
        if client_result.redacted_payload is None:
            return _blocked_after_network(
                injection, secret_material, mcp_envelope, request_body, safe_endpoint,
                safe_release_ref, safe_execution_ref, release.release_id,
                "mcp_credentialed_http_response_not_json_object", client_result.status_code,
            )
        return _result(
            decision="executed",
            injection=injection,
            secret_material=secret_material,
            mcp_envelope=mcp_envelope,
            request_body=request_body,
            transport_endpoint=safe_endpoint,
            release_ref=safe_release_ref,
            execution_ref=safe_execution_ref,
            release_id=release.release_id,
            execution_id=_execution_id(injection, mcp_envelope, request_body, safe_endpoint, safe_execution_ref),
            mcp_credentialed_http=True,
            sealed_credential_bound=True,
            mcp_envelope_bound=True,
            mcp_request_body_bound=True,
            local_http_loopback=True,
            tool_invoked=True,
            live_transport_enabled=True,
            execution_allowed=True,
            network_opened=True,
            handler_executed=True,
            credential_material_accessed=True,
            material_released_to_consumer=True,
            status_code=client_result.status_code,
            latency_ms=client_result.latency_ms,
            redacted_response=client_result.redacted_payload,
        )


def _blocked_after_network(
    injection: Optional[LiveCredentialInjectionResult],
    secret_material: Optional[LiveSecretMaterialResult],
    mcp_envelope: Optional[LiveMcpRequestResult],
    request_body: Optional[LiveMcpRequestBodyResult],
    transport_endpoint: Optional[str],
    release_ref: Optional[str],
    execution_ref: Optional[str],
    release_id: Optional[str],
    reason: str,
    status_code: Optional[int],
) -> LiveMcpCredentialedHttpResult:
    return _result(
        decision="blocked",
        injection=injection,
        secret_material=secret_material,
        mcp_envelope=mcp_envelope,
        request_body=request_body,
        transport_endpoint=transport_endpoint,
        release_ref=release_ref,
        execution_ref=execution_ref,
        release_id=release_id,
        blocked_reasons=(reason,),
        network_opened=True,
        credential_material_accessed=True,
        material_released_to_consumer=True,
        status_code=status_code,
    )


def _execution_id(
    injection: Optional[LiveCredentialInjectionResult],
    mcp_envelope: Optional[LiveMcpRequestResult],
    request_body: Optional[LiveMcpRequestBodyResult],
    transport_endpoint: Optional[str],
    execution_ref: Optional[str],
) -> str:
    payload = {
        "body_id": None if request_body is None else request_body.body_id,
        "execution_ref": execution_ref,
        "injection_id": None if injection is None else injection.injection_id,
        "request_envelope_id": None if mcp_envelope is None else mcp_envelope.request_envelope_id,
        "transport_endpoint": transport_endpoint,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-mcp-credentialed-http-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveMcpCredentialedHttpDecision,
    injection: Optional[LiveCredentialInjectionResult],
    secret_material: Optional[LiveSecretMaterialResult],
    mcp_envelope: Optional[LiveMcpRequestResult],
    request_body: Optional[LiveMcpRequestBodyResult],
    transport_endpoint: Optional[str],
    release_ref: Optional[str],
    execution_ref: Optional[str],
    blocked_reasons: tuple[str, ...] = (),
    release_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    status_code: Optional[int] = None,
    latency_ms: Optional[int] = None,
    redacted_response: Optional[dict[str, JsonValue]] = None,
    **flags: bool,
) -> LiveMcpCredentialedHttpResult:
    result = LiveMcpCredentialedHttpResult(
        decision=decision,
        execution_id=execution_id,
        release_id=release_id,
        injection_id=None if injection is None else injection.injection_id,
        material_proof_id=None if secret_material is None else secret_material.material_proof_id,
        request_envelope_id=None if mcp_envelope is None else mcp_envelope.request_envelope_id,
        body_id=None if request_body is None else request_body.body_id,
        transport_endpoint=transport_endpoint,
        transport_endpoint_host=None if transport_endpoint is None else mcp_endpoint_host(transport_endpoint),
        execution_ref=execution_ref,
        release_ref=release_ref,
        cleanup_receipt=_CLEANUP_RECEIPT if flags.get("network_opened") or decision == "executed" else None,
        blocked_reasons=blocked_reasons,
        status_code=status_code,
        latency_ms=latency_ms,
        redacted_response=redacted_response,
        **flags,
    )
    return result.model_copy(update={"no_secret_echo": no_secret_echo(result.to_payload())})
