from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_secret_material_runtime import LiveSecretMaterialResult
from zeus_agent.live_transport_lease_runtime import LiveTransportLeaseResult
from zeus_agent.mcp_runtime import default_mcp_catalog_entries
from zeus_agent.security.credentials import redact_secret_spans

LiveMcpRequestDecision = Literal["prepared", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
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


class LiveMcpRequestResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveMcpRequestDecision
    request_envelope_id: Optional[str]
    server_id: str
    tool_name: str
    endpoint: str
    endpoint_host: Optional[str]
    transport_lease_id: Optional[str]
    material_proof_id: Optional[str]
    arguments_digest: Optional[str] = None
    blocked_reasons: tuple[str, ...] = ()
    request_prepared: bool = False
    tool_allowlisted: bool = False
    secret_material_verified: bool = False
    server_started: bool = False
    resources_enabled: bool = False
    prompts_enabled: bool = False
    tool_invoked: bool = False
    credential_material_accessed: bool = False
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


class LiveMcpRequestRuntime:
    def prepare(
        self,
        *,
        transport_lease: Optional[LiveTransportLeaseResult],
        secret_material: Optional[LiveSecretMaterialResult],
        server_id: str,
        tool_name: str,
        endpoint: str,
        arguments: dict[str, JsonValue],
    ) -> LiveMcpRequestResult:
        safe_server_id = redact_secret_spans(server_id.strip())
        safe_tool_name = redact_secret_spans(tool_name.strip())
        safe_endpoint = redact_secret_spans(endpoint.strip())
        safe_arguments = _safe_arguments(arguments)
        endpoint_host = _endpoint_host(safe_endpoint)
        tool_allowlisted = _tool_allowlisted(server_id=safe_server_id, tool_name=safe_tool_name)
        reasons = list(_transport_reasons(transport_lease))
        reasons.extend(_secret_material_reasons(secret_material))
        if not tool_allowlisted:
            reasons.append("mcp_tool_not_allowlisted")
        if endpoint_host is None:
            reasons.append("malformed_mcp_endpoint")
        if (
            endpoint_host is not None
            and transport_lease is not None
            and transport_lease.network_host != endpoint_host
        ):
            reasons.append("mcp_endpoint_not_lease_bound")
        if reasons:
            return _result(
                decision="blocked",
                server_id=safe_server_id,
                tool_name=safe_tool_name,
                endpoint=safe_endpoint,
                endpoint_host=endpoint_host,
                transport_lease=transport_lease,
                secret_material=secret_material,
                arguments=safe_arguments,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
                tool_allowlisted=tool_allowlisted,
            )
        return _result(
            decision="prepared",
            server_id=safe_server_id,
            tool_name=safe_tool_name,
            endpoint=safe_endpoint,
            endpoint_host=endpoint_host,
            transport_lease=transport_lease,
            secret_material=secret_material,
            arguments=safe_arguments,
            request_envelope_id=_request_envelope_id(
                transport_lease=transport_lease,
                secret_material=secret_material,
                server_id=safe_server_id,
                tool_name=safe_tool_name,
                endpoint=safe_endpoint,
                arguments=safe_arguments,
            ),
            request_prepared=True,
            tool_allowlisted=True,
            secret_material_verified=True,
        )


def _transport_reasons(transport_lease: Optional[LiveTransportLeaseResult]) -> tuple[str, ...]:
    if transport_lease is None:
        return ("transport_lease_required",)
    reasons = []
    if transport_lease.decision != "bound" or not transport_lease.transport_lease_bound:
        reasons.append("transport_lease_not_bound")
    if transport_lease.runtime_kind != "mcp":
        reasons.append("transport_lease_surface_not_mcp")
    if transport_lease.live_transport_enabled or transport_lease.network_opened:
        reasons.append("transport_lease_side_effect_detected")
    if transport_lease.handler_executed or transport_lease.external_delivery_opened:
        reasons.append("transport_lease_side_effect_detected")
    if transport_lease.credential_material_accessed or transport_lease.live_production_claimed:
        reasons.append("transport_lease_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _secret_material_reasons(secret_material: Optional[LiveSecretMaterialResult]) -> tuple[str, ...]:
    if secret_material is None:
        return ("secret_material_proof_required",)
    reasons = []
    if secret_material.decision != "available" or not secret_material.material_available:
        reasons.append("secret_material_not_available")
    if secret_material.raw_secret_returned or secret_material.material_released:
        reasons.append("secret_material_leak_detected")
    if secret_material.network_opened or secret_material.external_delivery_opened:
        reasons.append("secret_material_side_effect_detected")
    if secret_material.live_production_claimed:
        reasons.append("secret_material_side_effect_detected")
    return tuple(dict.fromkeys(reasons))


def _tool_allowlisted(*, server_id: str, tool_name: str) -> bool:
    for entry in default_mcp_catalog_entries():
        if entry.server_id == server_id:
            return tool_name in set(entry.include_tools)
    return False


def _endpoint_host(endpoint: str) -> Optional[str]:
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"https", "http"}:
        return None
    if parsed.hostname is None or parsed.hostname.strip() == "":
        return None
    return parsed.hostname


def _safe_arguments(arguments: dict[str, JsonValue]) -> dict[str, JsonValue]:
    safe_payload: dict[str, JsonValue] = {}
    for key, value in arguments.items():
        safe_key = redact_secret_spans(str(key))
        if isinstance(value, str):
            safe_payload[safe_key] = redact_secret_spans(value)
        else:
            safe_payload[safe_key] = value
    return safe_payload


def _arguments_digest(arguments: dict[str, JsonValue]) -> str:
    encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _request_envelope_id(
    *,
    transport_lease: Optional[LiveTransportLeaseResult],
    secret_material: Optional[LiveSecretMaterialResult],
    server_id: str,
    tool_name: str,
    endpoint: str,
    arguments: dict[str, JsonValue],
) -> str:
    payload = {
        "arguments_digest": _arguments_digest(arguments),
        "endpoint": endpoint,
        "material_proof_id": None if secret_material is None else secret_material.material_proof_id,
        "server_id": server_id,
        "tool_name": tool_name,
        "transport_lease_id": None if transport_lease is None else transport_lease.transport_lease_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-mcp-request-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _result(
    *,
    decision: LiveMcpRequestDecision,
    server_id: str,
    tool_name: str,
    endpoint: str,
    endpoint_host: Optional[str],
    transport_lease: Optional[LiveTransportLeaseResult],
    secret_material: Optional[LiveSecretMaterialResult],
    arguments: dict[str, JsonValue],
    request_envelope_id: Optional[str] = None,
    blocked_reasons: tuple[str, ...] = (),
    request_prepared: bool = False,
    tool_allowlisted: bool = False,
    secret_material_verified: bool = False,
) -> LiveMcpRequestResult:
    result = LiveMcpRequestResult(
        decision=decision,
        request_envelope_id=request_envelope_id,
        server_id=server_id,
        tool_name=tool_name,
        endpoint=endpoint,
        endpoint_host=endpoint_host,
        transport_lease_id=None if transport_lease is None else transport_lease.transport_lease_id,
        material_proof_id=None if secret_material is None else secret_material.material_proof_id,
        arguments_digest=_arguments_digest(arguments) if arguments else None,
        blocked_reasons=blocked_reasons,
        request_prepared=request_prepared,
        tool_allowlisted=tool_allowlisted,
        secret_material_verified=secret_material_verified,
        server_started=False,
        resources_enabled=False,
        prompts_enabled=False,
        tool_invoked=False,
        credential_material_accessed=False,
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


def _no_secret_echo(result: LiveMcpRequestResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
