from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.security.credentials import redact_secret_spans

SecretResolverDecision = Literal["planned", "blocked"]
SecretResolverSurfaceKind = Literal["provider", "mcp", "gateway"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_SURFACE_KINDS: Final = {"provider", "mcp", "gateway"}
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


class SecretResolverPlanResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: SecretResolverDecision
    resolver_plan_id: Optional[str]
    surface_kind: Optional[SecretResolverSurfaceKind]
    surface_id: str
    credential_scope: Optional[str]
    binding_source: Optional[str] = None
    env_ref: Optional[str] = None
    vault_ref: Optional[str] = None
    expected_endpoint: Optional[str] = None
    target_endpoint: Optional[str] = None
    endpoint_binding_valid: bool = False
    material_access_allowed: bool = False
    blocked_reasons: tuple[str, ...]
    env_value_read: bool = False
    vault_value_read: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class SecretResolverPlanRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home

    def plan(
        self,
        *,
        surface_kind: str,
        surface_id: str,
        credential_scope: Optional[str],
        expected_endpoint: Optional[str] = None,
        allow_material_access: bool = False,
    ) -> SecretResolverPlanResult:
        safe_surface_id = redact_secret_spans(surface_id.strip())
        safe_expected_endpoint = _safe_optional(expected_endpoint)
        safe_scope = _safe_optional(credential_scope)
        safe_kind = surface_kind.strip()
        reasons = []
        if safe_kind not in _SURFACE_KINDS:
            reasons.append("unsupported_surface_kind")
        if allow_material_access:
            reasons.append("secret_material_resolution_requires_live_operator")

        binding = None
        target_endpoint = None
        if safe_scope is not None and safe_kind in _SURFACE_KINDS:
            binding = _matching_binding(
                CredentialReadinessRuntime(self.home).build().credential_bindings,
                surface_kind=safe_kind,
                surface_id=safe_surface_id,
                credential_scope=safe_scope,
            )
            if binding is None:
                reasons.append("credential_binding_not_ready")
            else:
                target_endpoint = _target_endpoint(binding)
                endpoint_reason = _endpoint_reason(
                    expected_endpoint=safe_expected_endpoint,
                    target_endpoint=target_endpoint,
                )
                if endpoint_reason is not None:
                    reasons.append(endpoint_reason)

        blocked_reasons = tuple(dict.fromkeys(reasons))
        decision: SecretResolverDecision = "blocked" if blocked_reasons else "planned"
        result = SecretResolverPlanResult(
            decision=decision,
            resolver_plan_id=_resolver_plan_id(
                surface_kind=safe_kind,
                surface_id=safe_surface_id,
                credential_scope=safe_scope,
                expected_endpoint=safe_expected_endpoint,
            )
            if decision == "planned"
            else None,
            surface_kind=safe_kind if safe_kind in _SURFACE_KINDS else None,
            surface_id=safe_surface_id,
            credential_scope=safe_scope,
            binding_source=_optional_binding_text(binding, "binding_source"),
            env_ref=_optional_binding_text(binding, "env_ref"),
            vault_ref=_optional_binding_text(binding, "vault_ref"),
            expected_endpoint=safe_expected_endpoint,
            target_endpoint=target_endpoint,
            endpoint_binding_valid=_endpoint_binding_valid(safe_expected_endpoint, target_endpoint),
            material_access_allowed=False,
            blocked_reasons=blocked_reasons,
            env_value_read=False,
            vault_value_read=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            credential_material_accessed=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _safe_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "":
        return None
    return redact_secret_spans(stripped)


def _matching_binding(
    bindings: tuple[dict[str, JsonValue], ...],
    *,
    surface_kind: str,
    surface_id: str,
    credential_scope: str,
) -> Optional[dict[str, JsonValue]]:
    for binding in bindings:
        if not bool(binding.get("binding_configured", False)):
            continue
        if binding.get("surface_kind") != surface_kind:
            continue
        if binding.get("credential_scope") != credential_scope:
            continue
        binding_surface_id = str(binding.get("surface_id", ""))
        if binding_surface_id == surface_id or binding_surface_id == _surface_suffix(surface_id):
            return binding
    return None


def _surface_suffix(surface_id: str) -> str:
    if "." not in surface_id:
        return surface_id
    return surface_id.rsplit(".", 1)[1]


def _target_endpoint(binding: dict[str, JsonValue]) -> Optional[str]:
    for key in ("target", "network_host", "source_ref", "server_id"):
        value = binding.get(key)
        if isinstance(value, str) and value.strip() != "":
            return redact_secret_spans(value.strip())
    return None


def _endpoint_reason(
    *,
    expected_endpoint: Optional[str],
    target_endpoint: Optional[str],
) -> Optional[str]:
    if expected_endpoint is None:
        return None
    if target_endpoint is None:
        return "credential_endpoint_missing"
    if expected_endpoint != target_endpoint:
        return "credential_endpoint_mismatch"
    return None


def _endpoint_binding_valid(
    expected_endpoint: Optional[str],
    target_endpoint: Optional[str],
) -> bool:
    if expected_endpoint is None:
        return target_endpoint is not None
    return expected_endpoint == target_endpoint


def _optional_binding_text(binding: Optional[dict[str, JsonValue]], key: str) -> Optional[str]:
    if binding is None:
        return None
    value = binding.get(key)
    if not isinstance(value, str) or value.strip() == "":
        return None
    return redact_secret_spans(value.strip())


def _resolver_plan_id(
    *,
    surface_kind: str,
    surface_id: str,
    credential_scope: Optional[str],
    expected_endpoint: Optional[str],
) -> str:
    payload = {
        "surface_kind": surface_kind,
        "surface_id": surface_id,
        "credential_scope": credential_scope,
        "expected_endpoint": expected_endpoint,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "secret-resolver-plan-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _no_secret_echo(result: SecretResolverPlanResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
