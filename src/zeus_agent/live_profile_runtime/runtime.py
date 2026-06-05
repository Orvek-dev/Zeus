from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from zeus_agent.credential_readiness_runtime import CredentialReadinessRuntime
from zeus_agent.gateway_settings_runtime import GatewaySettingsRuntime
from zeus_agent.mcp_settings_runtime import McpSettingsRuntime
from zeus_agent.model_settings_runtime import ModelSettingsRuntime
from zeus_agent.security.credentials import redact_secret_spans

LiveProfileDecision = Literal["profile", "blocked"]
LiveProfileSurfaceKind = Literal["provider", "mcp", "gateway"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
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


class LiveProfileResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveProfileDecision
    surface_id: str
    surface_kind: Optional[LiveProfileSurfaceKind] = None
    approval_id: Optional[str] = None
    capability_id: Optional[str] = None
    blocked_reasons: tuple[str, ...] = ()
    redacted_input: Optional[str] = None
    configuration_context: dict[str, JsonValue] = Field(default_factory=dict)
    preflight_request_template: dict[str, JsonValue] = Field(default_factory=dict)
    lease_template: dict[str, JsonValue] = Field(default_factory=dict)
    pipeline_commands: tuple[str, ...] = ()
    pipeline_stage_count: int = 0
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveProfileRuntime:
    def __init__(self, home: Optional[Path] = None) -> None:
        self.home = home

    def build(
        self,
        *,
        surface_id: str,
        principal_id: str,
        objective_id: str,
        delivery_target: Optional[str] = None,
        allowlisted_delivery_targets: tuple[str, ...] = (),
    ) -> LiveProfileResult:
        safe_surface_id, surface_secret = _safe_field(surface_id)
        safe_principal_id, principal_secret = _safe_field(principal_id)
        safe_objective_id, objective_secret = _safe_field(objective_id)
        safe_delivery_target, delivery_secret = _safe_optional_field(delivery_target)
        safe_allowlist, allowlist_secret = _safe_tuple(allowlisted_delivery_targets)
        profile = _profile_for_surface(safe_surface_id)
        configuration_context = build_live_configuration_context(self.home)
        reasons = []
        if profile is None:
            reasons.append("unknown_live_surface_profile")
        if surface_secret or principal_secret or objective_secret or delivery_secret or allowlist_secret:
            reasons.append("secret_like_profile_field")
        if reasons or profile is None:
            result = LiveProfileResult(
                decision="blocked",
                surface_id=safe_surface_id,
                blocked_reasons=tuple(dict.fromkeys(reasons)),
                redacted_input=_join_redacted_inputs(
                    (
                        safe_surface_id if surface_secret else None,
                        safe_principal_id if principal_secret else None,
                        safe_objective_id if objective_secret else None,
                        safe_delivery_target if delivery_secret else None,
                    ),
                    safe_allowlist if allowlist_secret else (),
                ),
                configuration_context=configuration_context,
                execution_allowed=False,
                live_transport_enabled=False,
                live_production_claimed=False,
            )
            return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})

        resolved_delivery_target, resolved_allowlist = _resolve_delivery_from_config(
            surface_id=safe_surface_id,
            delivery_target=safe_delivery_target,
            allowlisted_delivery_targets=safe_allowlist,
            configuration_context=configuration_context,
        )
        preflight = _preflight_template(
            profile,
            principal_id=safe_principal_id,
            objective_id=safe_objective_id,
            delivery_target=resolved_delivery_target,
            allowlisted_delivery_targets=resolved_allowlist,
        )
        lease = _lease_template(
            profile,
            principal_id=safe_principal_id,
            objective_id=safe_objective_id,
        )
        result = LiveProfileResult(
            decision="profile",
            surface_id=safe_surface_id,
            surface_kind=profile["surface_kind"],
            approval_id=profile["approval_id"],
            capability_id=profile["capability_id"],
            blocked_reasons=(),
            configuration_context=configuration_context,
            preflight_request_template=preflight,
            lease_template=lease,
            pipeline_commands=_pipeline_commands(),
            pipeline_stage_count=4,
            execution_allowed=False,
            authority_granted=False,
            live_transport_enabled=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            credential_material_accessed=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _safe_field(value: str) -> tuple[str, bool]:
    redacted = redact_secret_spans(value)
    return redacted, redacted != value.strip()


def _safe_optional_field(value: Optional[str]) -> tuple[Optional[str], bool]:
    if value is None:
        return None, False
    return _safe_field(value)


def _safe_tuple(values: tuple[str, ...]) -> tuple[tuple[str, ...], bool]:
    safe_values = []
    secret_seen = False
    for value in values:
        safe_value, secret = _safe_field(value)
        safe_values.append(safe_value)
        secret_seen = secret_seen or secret
    return tuple(safe_values), secret_seen


def build_live_configuration_context(home: Optional[Path]) -> dict[str, JsonValue]:
    if home is None:
        return _empty_configuration_context()
    model = ModelSettingsRuntime(home).show()
    mcp = McpSettingsRuntime(home).list()
    gateway = GatewaySettingsRuntime(home).list()
    credential_readiness = CredentialReadinessRuntime(home).build()
    configured_servers = [
        str(server["server_id"])
        for server in mcp.configured_servers
        if isinstance(server.get("server_id"), str)
    ]
    configured_targets = [_safe_configured_gateway_target(target) for target in gateway.configured_targets]
    return {
        "config_source": "local_home",
        "model_preference": {
            "source": model.source,
            "provider_id": model.provider_id,
            "model_id": model.model_id,
            "requires_credential": model.requires_credential,
            "requires_network_lease": model.requires_network_lease,
            "network_opened": model.network_opened,
            "credential_material_accessed": model.credential_material_accessed,
        },
        "mcp_config": {
            "configured_server_count": mcp.configured_server_count,
            "configured_server_ids": configured_servers,
            "server_started": mcp.server_started,
            "network_opened": mcp.network_opened,
            "credential_material_accessed": mcp.credential_material_accessed,
        },
        "gateway_config": {
            "configured_target_count": gateway.configured_target_count,
            "configured_targets": configured_targets,
            "external_delivery_opened": gateway.external_delivery_opened,
            "network_opened": gateway.network_opened,
            "handler_executed": gateway.handler_executed,
            "credential_material_accessed": gateway.credential_material_accessed,
        },
        "credential_readiness": credential_readiness.to_payload(),
        "external_delivery_opened": gateway.external_delivery_opened,
        "network_opened": bool(model.network_opened or mcp.network_opened or gateway.network_opened),
        "handler_executed": bool(mcp.handler_executed or gateway.handler_executed),
        "credential_material_accessed": bool(
            model.credential_material_accessed
            or mcp.credential_material_accessed
            or gateway.credential_material_accessed
        ),
        "live_production_claimed": bool(
            model.live_production_claimed or mcp.live_production_claimed or gateway.live_production_claimed
        ),
    }


def _empty_configuration_context() -> dict[str, JsonValue]:
    return {
        "config_source": "none",
        "model_preference": {
            "source": "none",
            "provider_id": None,
            "model_id": None,
            "requires_credential": False,
            "requires_network_lease": False,
            "network_opened": False,
            "credential_material_accessed": False,
        },
        "mcp_config": {
            "configured_server_count": 0,
            "configured_server_ids": [],
            "server_started": False,
            "network_opened": False,
            "credential_material_accessed": False,
        },
        "gateway_config": {
            "configured_target_count": 0,
            "configured_targets": [],
            "external_delivery_opened": False,
            "network_opened": False,
            "handler_executed": False,
            "credential_material_accessed": False,
        },
        "credential_readiness": {
            "decision": "report",
            "required_binding_count": 0,
            "ready_binding_count": 0,
            "credential_bindings": [],
            "provider_requires_credential": False,
            "provider_id": "none",
            "provider_model_id": "none",
            "provider_credential_scope": None,
            "mcp_configured_server_count": 0,
            "mcp_required_binding_count": 0,
            "mcp_binding_status": "not_configured",
            "gateway_configured_target_count": 0,
            "ready_for_live_transport": True,
            "binding_registry_available": False,
            "env_value_read": False,
            "vault_value_read": False,
            "network_opened": False,
            "handler_executed": False,
            "external_delivery_opened": False,
            "credential_material_accessed": False,
            "no_secret_echo": True,
            "live_production_claimed": False,
        },
        "external_delivery_opened": False,
        "network_opened": False,
        "handler_executed": False,
        "credential_material_accessed": False,
        "live_production_claimed": False,
    }


def _safe_configured_gateway_target(target: dict[str, JsonValue]) -> dict[str, JsonValue]:
    raw_target = str(target["target"])
    safe_target = redact_secret_spans(raw_target)
    return {
        "adapter_id": str(target["adapter_id"]),
        "display_name": str(target["display_name"]),
        "target": safe_target,
        "state": str(target["state"]),
        "target_allowlisted": bool(target["target_allowlisted"]),
        "pairing_required": bool(target.get("pairing_required", True)),
        "pairing_configured": bool(target.get("pairing_configured", False)),
        "external_delivery_opened": False,
        "network_opened": False,
        "handler_executed": False,
    }


def _resolve_delivery_from_config(
    *,
    surface_id: str,
    delivery_target: Optional[str],
    allowlisted_delivery_targets: tuple[str, ...],
    configuration_context: dict[str, JsonValue],
) -> tuple[Optional[str], tuple[str, ...]]:
    if delivery_target is not None or allowlisted_delivery_targets:
        return delivery_target, allowlisted_delivery_targets
    adapter_id = _gateway_adapter_id(surface_id)
    if adapter_id is None:
        return delivery_target, allowlisted_delivery_targets
    gateway_config = configuration_context.get("gateway_config", {})
    if not isinstance(gateway_config, dict):
        return delivery_target, allowlisted_delivery_targets
    targets = gateway_config.get("configured_targets", [])
    if not isinstance(targets, list):
        return delivery_target, allowlisted_delivery_targets
    matching_targets = [
        str(item["target"])
        for item in targets
        if isinstance(item, dict)
        and item.get("adapter_id") == adapter_id
        and item.get("target_allowlisted") is True
        and isinstance(item.get("target"), str)
    ]
    deduped = tuple(dict.fromkeys(matching_targets))
    if not deduped:
        return delivery_target, allowlisted_delivery_targets
    return deduped[0], deduped


def _gateway_adapter_id(surface_id: str) -> Optional[str]:
    if not surface_id.startswith("gateway."):
        return None
    adapter_id = surface_id.split(".", 1)[1]
    if adapter_id == "":
        return None
    return adapter_id


def _profile_for_surface(surface_id: str) -> Optional[dict[str, JsonValue]]:
    profiles: dict[str, dict[str, JsonValue]] = {
        "provider.external.openai": {
            "surface_kind": "provider",
            "approval_id": "provider-live",
            "capability_id": "provider.external.generate",
            "credential_scope": "external.openai.readonly",
            "network_host": "api.openai.local",
            "source_pinned": True,
            "mcp_description": None,
        },
        "mcp.catalog": {
            "surface_kind": "mcp",
            "approval_id": "mcp-live",
            "capability_id": "mcp.echo",
            "credential_scope": None,
            "network_host": "mcp.local",
            "source_pinned": True,
            "mcp_description": "curated MCP catalog live-beta profile",
        },
        "gateway.slack": {
            "surface_kind": "gateway",
            "approval_id": "external-delivery",
            "capability_id": "gateway.webhook.dispatch",
            "credential_scope": "external.gateway.readonly",
            "network_host": "gateway.local",
            "source_pinned": False,
            "mcp_description": None,
        },
    }
    return profiles.get(surface_id)


def _preflight_template(
    profile: dict[str, JsonValue],
    *,
    principal_id: str,
    objective_id: str,
    delivery_target: Optional[str],
    allowlisted_delivery_targets: tuple[str, ...],
) -> dict[str, JsonValue]:
    surface_kind = str(profile["surface_kind"])
    template: dict[str, JsonValue] = {
        "preflight_id": "{0}.preflight".format(objective_id),
        "approval_id": str(profile["approval_id"]),
        "principal_id": principal_id,
        "objective_id": objective_id,
        "surface_kind": surface_kind,
        "surface_id": _surface_id_for_profile(profile),
        "capability_id": str(profile["capability_id"]),
        "evidence_target": "{0}.live_profile".format(objective_id),
        "credential_scope": profile["credential_scope"],
        "network_host": profile["network_host"],
        "approval_receipt_id": "<approval-receipt-id>",
        "approval_proof_hash": "<approval-proof-hash>",
        "probe_healthy": True,
        "source_pinned": bool(profile["source_pinned"]),
        "mcp_description": profile["mcp_description"],
        "delivery_target": delivery_target,
        "allowlisted_delivery_targets": list(allowlisted_delivery_targets),
        "budget_required": 1,
        "cleanup_required": True,
        "live_production_claim_requested": False,
    }
    return template


def _lease_template(
    profile: dict[str, JsonValue],
    *,
    principal_id: str,
    objective_id: str,
) -> dict[str, JsonValue]:
    credential_scope = profile["credential_scope"]
    return {
        "lease_id": "{0}.lease.live".format(objective_id),
        "objective_id": objective_id,
        "principal_id": principal_id,
        "run_id": "{0}.run.live".format(objective_id),
        "allowed_capabilities": [profile["capability_id"]],
        "credential_scopes": [] if credential_scope is None else [credential_scope],
        "network_hosts": [profile["network_host"]],
        "budget_limit": 100,
        "evidence_target": "{0}.live_profile".format(objective_id),
        "live_transport_allowed": True,
    }


def _surface_id_for_profile(profile: dict[str, JsonValue]) -> str:
    surface_kind = str(profile["surface_kind"])
    if surface_kind == "provider":
        return "provider.external.openai"
    if surface_kind == "mcp":
        return "mcp.catalog"
    return "gateway.slack"


def _pipeline_commands() -> tuple[str, ...]:
    return (
        "zeus approval-receipt --json",
        "zeus live-preflight --json",
        "zeus live-handoff --json",
        "zeus live-execute-plan --json",
    )


def _join_redacted_inputs(
    values: tuple[Optional[str], ...],
    allowlisted_values: tuple[str, ...],
) -> Optional[str]:
    redacted_values = [value for value in values if value is not None]
    redacted_values.extend(allowlisted_values)
    deduped = tuple(dict.fromkeys(redacted_values))
    if not deduped:
        return None
    return ";".join(deduped)


def _no_secret_echo(result: LiveProfileResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
