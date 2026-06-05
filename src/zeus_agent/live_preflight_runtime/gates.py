from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

from pydantic import JsonValue

from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.gateway_pairing_runtime import GatewayPairingRuntime


class LivePreflightGateRequest(Protocol):
    surface_kind: str
    surface_id: str
    credential_scope: Optional[str]
    delivery_target: Optional[str]


def credential_readiness_payload(home: Optional[Path]) -> Optional[dict[str, JsonValue]]:
    if home is None:
        return None
    return CredentialReadinessRuntime(home).build().to_payload()


def credential_binding_reasons(
    request: LivePreflightGateRequest,
    credential_readiness: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if request.credential_scope is None or credential_readiness is None:
        return ()
    bindings = credential_readiness.get("credential_bindings", [])
    if not isinstance(bindings, list):
        return ("credential_binding_required",)
    candidates = [
        item
        for item in bindings
        if isinstance(item, dict)
        and item.get("surface_kind") == request.surface_kind
        and item.get("credential_scope") == request.credential_scope
        and _surface_matches(request.surface_id, item)
    ]
    if not candidates:
        return ("credential_binding_required",)
    if not any(bool(item.get("binding_configured", False)) for item in candidates):
        return ("credential_binding_not_ready",)
    return ()


def gateway_pairing_payload(home: Optional[Path]) -> Optional[dict[str, JsonValue]]:
    if home is None:
        return None
    return GatewayPairingRuntime(home).list().to_payload()


def gateway_pairing_reasons(
    request: LivePreflightGateRequest,
    gateway_pairing: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if request.surface_kind != "gateway" or gateway_pairing is None:
        return ()
    if request.delivery_target is None:
        return ()
    pairings = gateway_pairing.get("pairings", [])
    if not isinstance(pairings, list):
        return ("gateway_pairing_required",)
    if not any(_pairing_matches(request, pairing) for pairing in pairings if isinstance(pairing, dict)):
        return ("gateway_pairing_not_ready",)
    return ()


def _surface_matches(request_surface_id: str, binding: dict[str, object]) -> bool:
    binding_surface_id = binding.get("surface_id")
    if not isinstance(binding_surface_id, str) or binding_surface_id == "":
        return False
    return request_surface_id == binding_surface_id or request_surface_id.endswith(
        ".{0}".format(binding_surface_id),
    )


def _pairing_matches(request: LivePreflightGateRequest, pairing: dict[str, object]) -> bool:
    adapter_id = pairing.get("adapter_id")
    target = pairing.get("target")
    if not isinstance(adapter_id, str) or not isinstance(target, str):
        return False
    return (
        bool(pairing.get("pairing_configured", False))
        and request.delivery_target == target
        and (request.surface_id == adapter_id or request.surface_id.endswith(".{0}".format(adapter_id)))
    )
