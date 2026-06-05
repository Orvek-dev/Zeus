from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.gateway_settings_runtime import GatewaySettingsRuntime
from zeus_agent.mcp_settings_runtime import McpSettingsRuntime
from zeus_agent.model_settings_runtime import ModelSettingsRuntime
from zeus_agent.security.credentials import redact_secret_spans

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_GATEWAY_CREDENTIAL_SCOPE: Final = "external.gateway.readonly"
_SAFE_SCOPE_PATTERN: Final = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
_SAFE_SURFACE_ID_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9._-]{0,96}$")
_SAFE_ENV_REF_PATTERN: Final = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
_SAFE_VAULT_REF_PATTERN: Final = re.compile(r"^vault://[a-z0-9][a-z0-9._/-]{2,200}$")
_SECRET_VALUE_PREFIXES: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
)
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


class CredentialReadinessResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: str
    required_binding_count: int
    ready_binding_count: int
    credential_bindings: tuple[dict[str, JsonValue], ...]
    provider_requires_credential: bool
    provider_id: str
    provider_model_id: str
    provider_credential_scope: Optional[str] = None
    mcp_configured_server_count: int
    mcp_required_binding_count: int = 0
    mcp_binding_status: str
    gateway_configured_target_count: int
    ready_for_live_transport: bool
    binding_registry_available: bool = False
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


class CredentialBindingResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: str
    binding: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    redacted_input: Optional[str] = None
    binding_registry_available: bool = False
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


class CredentialReadinessRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.config_path = home / "credential-bindings.json"

    def build(self) -> CredentialReadinessResult:
        model = ModelSettingsRuntime(self.home).show()
        mcp = McpSettingsRuntime(self.home).list()
        gateway = GatewaySettingsRuntime(self.home).list()
        registry = self._configured_bindings()
        bindings = []
        if model.credential_scope_label is not None:
            bindings.append(
                _provider_binding(
                    provider_id=model.provider_id,
                    model_id=model.model_id,
                    credential_scope=model.credential_scope_label,
                    network_host=model.network_host,
                    registry=registry,
                ),
            )
        mcp_required_binding_count = 0
        for server in mcp.configured_servers:
            credential_scope = server.get("credential_scope")
            if bool(server.get("requires_credential", False)) and isinstance(credential_scope, str):
                mcp_required_binding_count += 1
                bindings.append(_mcp_binding(server, registry=registry))
        for target in gateway.configured_targets:
            if bool(target.get("auth_required", True)):
                bindings.append(_gateway_binding(target, registry=registry))
        ready_count = sum(1 for item in bindings if bool(item["binding_configured"]))
        result = CredentialReadinessResult(
            decision="report",
            required_binding_count=len(bindings),
            ready_binding_count=ready_count,
            credential_bindings=tuple(bindings),
            provider_requires_credential=model.requires_credential,
            provider_id=model.provider_id,
            provider_model_id=model.model_id,
            provider_credential_scope=model.credential_scope_label,
            mcp_configured_server_count=mcp.configured_server_count,
            mcp_required_binding_count=mcp_required_binding_count,
            mcp_binding_status=_mcp_binding_status(
                configured_server_count=mcp.configured_server_count,
                required_binding_count=mcp_required_binding_count,
            ),
            gateway_configured_target_count=gateway.configured_target_count,
            ready_for_live_transport=len(bindings) == ready_count,
            binding_registry_available=self.config_path.exists(),
            env_value_read=False,
            vault_value_read=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            credential_material_accessed=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})

    def bind(
        self,
        *,
        surface_kind: str,
        surface_id: str,
        credential_scope: str,
        env_ref: Optional[str] = None,
        vault_ref: Optional[str] = None,
    ) -> CredentialBindingResult:
        blocked_reasons, redacted_input = _binding_blockers(
            surface_kind=surface_kind,
            surface_id=surface_id,
            credential_scope=credential_scope,
            env_ref=env_ref,
            vault_ref=vault_ref,
        )
        if blocked_reasons:
            return _binding_result(
                decision="blocked",
                binding=None,
                blocked_reasons=blocked_reasons,
                redacted_input=redacted_input,
                registry_available=self.config_path.exists(),
            )

        clean_surface_kind = surface_kind.strip()
        clean_surface_id = surface_id.strip()
        clean_scope = credential_scope.strip()
        clean_env_ref = env_ref.strip() if env_ref is not None else None
        clean_vault_ref = vault_ref.strip() if vault_ref is not None else None
        binding = {
            "surface_kind": clean_surface_kind,
            "surface_id": clean_surface_id,
            "credential_scope": clean_scope,
            "env_ref": clean_env_ref,
            "vault_ref": clean_vault_ref,
            "binding_source": _binding_source(env_ref=clean_env_ref, vault_ref=clean_vault_ref),
            "binding_configured": True,
            "env_value_read": False,
            "vault_value_read": False,
            "credential_material_accessed": False,
            "network_opened": False,
            "handler_executed": False,
            "external_delivery_opened": False,
            "live_production_claimed": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        configured = [
            item
            for item in self._configured_bindings()
            if not _same_binding(
                item,
                surface_kind=clean_surface_kind,
                surface_id=clean_surface_id,
                credential_scope=clean_scope,
            )
        ]
        configured.append(binding)
        self.home.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps({"bindings": configured}, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return _binding_result(
            decision="bound",
            binding=binding,
            blocked_reasons=(),
            redacted_input=None,
            registry_available=True,
        )

    def _configured_bindings(self) -> tuple[dict[str, JsonValue], ...]:
        if not self.config_path.exists():
            return ()
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ()
        if not isinstance(payload, dict):
            return ()
        raw_bindings = payload.get("bindings", [])
        if not isinstance(raw_bindings, list):
            return ()
        configured = []
        for item in raw_bindings:
            if not isinstance(item, dict):
                continue
            normalized = _normalize_registry_binding(item)
            if normalized is not None:
                configured.append(normalized)
        return tuple(configured)


def _provider_binding(
    *,
    provider_id: str,
    model_id: str,
    credential_scope: str,
    network_host: Optional[str],
    registry: tuple[dict[str, JsonValue], ...],
) -> dict[str, JsonValue]:
    configured = _find_registry_binding(
        registry,
        surface_kind="provider",
        surface_id=provider_id,
        credential_scope=credential_scope,
    )
    return {
        "surface_kind": "provider",
        "surface_id": provider_id,
        "provider_id": provider_id,
        "model_id": model_id,
        "credential_scope": credential_scope,
        "network_host": network_host,
        "binding_required": True,
        "binding_configured": configured is not None,
        "binding_registry_available": configured is not None,
        "binding_source": _configured_binding_source(configured),
        "env_ref": _configured_env_ref(configured, default=_env_ref(credential_scope)),
        "env_value_read": False,
        "vault_ref": _configured_vault_ref(configured, default=_vault_ref(credential_scope)),
        "vault_value_read": False,
        "pairing_required": False,
        "pairing_configured": False,
        "target_allowlisted": None,
        "credential_material_accessed": False,
        "network_opened": False,
        "handler_executed": False,
        "external_delivery_opened": False,
        "live_production_claimed": False,
    }


def _mcp_binding(
    server: dict[str, JsonValue],
    *,
    registry: tuple[dict[str, JsonValue], ...],
) -> dict[str, JsonValue]:
    server_id = str(server.get("server_id", "unknown"))
    credential_scope = str(server.get("credential_scope", ""))
    configured = _find_registry_binding(
        registry,
        surface_kind="mcp",
        surface_id=server_id,
        credential_scope=credential_scope,
    )
    include_tools = server.get("include_tools", [])
    exclude_tools = server.get("exclude_tools", [])
    return {
        "surface_kind": "mcp",
        "surface_id": server_id,
        "server_id": server_id,
        "display_name": str(server.get("display_name", server_id)),
        "transport": str(server.get("transport", "stdio")),
        "source_ref": str(server.get("source_ref", "")),
        "source_pinned": bool(server.get("source_pinned", False)),
        "include_tools": [str(value) for value in include_tools] if isinstance(include_tools, list) else [],
        "exclude_tools": [str(value) for value in exclude_tools] if isinstance(exclude_tools, list) else [],
        "resources_enabled": False,
        "prompts_enabled": False,
        "server_started": False,
        "credential_scope": credential_scope,
        "binding_required": True,
        "binding_configured": configured is not None,
        "binding_registry_available": configured is not None,
        "binding_source": _configured_binding_source(configured),
        "env_ref": _configured_env_ref(configured, default=_env_ref(credential_scope)),
        "env_value_read": False,
        "vault_ref": _configured_vault_ref(configured, default=_vault_ref(credential_scope)),
        "vault_value_read": False,
        "credential_material_accessed": False,
        "network_opened": False,
        "handler_executed": False,
        "external_delivery_opened": False,
        "live_production_claimed": False,
    }


def _gateway_binding(
    target: dict[str, JsonValue],
    *,
    registry: tuple[dict[str, JsonValue], ...],
) -> dict[str, JsonValue]:
    adapter_id = str(target.get("adapter_id", "unknown"))
    safe_target = redact_secret_spans(str(target.get("target", "")))
    configured = _find_registry_binding(
        registry,
        surface_kind="gateway",
        surface_id=adapter_id,
        credential_scope=_GATEWAY_CREDENTIAL_SCOPE,
    )
    return {
        "surface_kind": "gateway",
        "surface_id": adapter_id,
        "adapter_id": adapter_id,
        "target": safe_target,
        "credential_scope": _GATEWAY_CREDENTIAL_SCOPE,
        "binding_required": True,
        "binding_configured": configured is not None,
        "binding_registry_available": configured is not None,
        "binding_source": _configured_binding_source(configured),
        "env_ref": _configured_env_ref(configured, default=_env_ref(_GATEWAY_CREDENTIAL_SCOPE, suffix=adapter_id)),
        "env_value_read": False,
        "vault_ref": _configured_vault_ref(configured, default=_vault_ref(_GATEWAY_CREDENTIAL_SCOPE, suffix=adapter_id)),
        "vault_value_read": False,
        "pairing_required": bool(target.get("pairing_required", True)),
        "pairing_configured": False,
        "target_allowlisted": bool(target.get("target_allowlisted", False)),
        "delivery_target_allowlist_required": bool(target.get("delivery_target_allowlist_required", True)),
        "credential_material_accessed": False,
        "network_opened": False,
        "handler_executed": False,
        "external_delivery_opened": False,
        "live_production_claimed": False,
    }


def _mcp_binding_status(*, configured_server_count: int, required_binding_count: int) -> str:
    if configured_server_count == 0:
        return "not_configured"
    if required_binding_count == 0:
        return "configured_no_credential_required"
    return "configured_requires_credentials"


def _env_ref(scope: str, *, suffix: Optional[str] = None) -> str:
    pieces = [scope.replace(".", "_").replace("-", "_").upper()]
    if suffix is not None and suffix.strip() != "":
        pieces.append(suffix.replace(".", "_").replace("-", "_").upper())
    return "ZEUS_CREDENTIAL_" + "_".join(pieces)


def _vault_ref(scope: str, *, suffix: Optional[str] = None) -> str:
    pieces = scope.replace(".", "/").replace("-", "_")
    if suffix is not None and suffix.strip() != "":
        pieces = pieces + "/" + suffix.replace(".", "_").replace("-", "_")
    return "vault://zeus/" + pieces


def _binding_blockers(
    *,
    surface_kind: str,
    surface_id: str,
    credential_scope: str,
    env_ref: Optional[str],
    vault_ref: Optional[str],
) -> tuple[tuple[str, ...], Optional[str]]:
    reasons = []
    redacted_inputs = []
    if surface_kind.strip() not in {"provider", "gateway", "mcp"}:
        reasons.append("unsupported_surface_kind")
        redacted_inputs.append(redact_secret_spans(surface_kind))
    if _SAFE_SURFACE_ID_PATTERN.fullmatch(surface_id.strip()) is None:
        reasons.append("unsafe_surface_id")
        redacted_inputs.append(redact_secret_spans(surface_id))
    if _SAFE_SCOPE_PATTERN.fullmatch(credential_scope.strip()) is None:
        reasons.append("unsafe_credential_scope")
        redacted_inputs.append(redact_secret_spans(credential_scope))
    if env_ref is None and vault_ref is None:
        reasons.append("missing_credential_reference")
    if env_ref is not None and not _safe_env_ref(env_ref):
        reasons.append("unsafe_credential_reference")
        redacted_inputs.append(redact_secret_spans(env_ref))
    if vault_ref is not None and not _safe_vault_ref(vault_ref):
        reasons.append("unsafe_credential_reference")
        redacted_inputs.append(redact_secret_spans(vault_ref))
    return tuple(dict.fromkeys(reasons)), _join_redacted_inputs(redacted_inputs)


def _safe_env_ref(env_ref: str) -> bool:
    value = env_ref.strip()
    if _secret_value_like(value):
        return False
    return _SAFE_ENV_REF_PATTERN.fullmatch(value) is not None


def _safe_vault_ref(vault_ref: str) -> bool:
    value = vault_ref.strip()
    if _secret_value_like(value):
        return False
    return _SAFE_VAULT_REF_PATTERN.fullmatch(value) is not None


def _secret_value_like(value: str) -> bool:
    lowered = value.strip().lower()
    if any(lowered.startswith(prefix) for prefix in _SECRET_VALUE_PREFIXES):
        return True
    return "bearer " in lowered or "-----begin" in lowered or "=" in lowered or "\n" in lowered or "\t" in lowered


def _join_redacted_inputs(values: list[str]) -> Optional[str]:
    clean_values = [value for value in values if value != ""]
    if not clean_values:
        return None
    return " | ".join(clean_values)


def _binding_source(*, env_ref: Optional[str], vault_ref: Optional[str]) -> str:
    if env_ref is not None and vault_ref is not None:
        return "env_ref+vault_ref"
    if env_ref is not None:
        return "env_ref"
    return "vault_ref"


def _normalize_registry_binding(item: dict[str, object]) -> Optional[dict[str, JsonValue]]:
    surface_kind = str(item.get("surface_kind", "")).strip()
    surface_id = str(item.get("surface_id", "")).strip()
    credential_scope = str(item.get("credential_scope", "")).strip()
    env_ref_value = item.get("env_ref")
    vault_ref_value = item.get("vault_ref")
    env_ref = str(env_ref_value).strip() if isinstance(env_ref_value, str) else None
    vault_ref = str(vault_ref_value).strip() if isinstance(vault_ref_value, str) else None
    blocked, _ = _binding_blockers(
        surface_kind=surface_kind,
        surface_id=surface_id,
        credential_scope=credential_scope,
        env_ref=env_ref,
        vault_ref=vault_ref,
    )
    if blocked:
        return None
    return {
        "surface_kind": surface_kind,
        "surface_id": surface_id,
        "credential_scope": credential_scope,
        "env_ref": env_ref,
        "vault_ref": vault_ref,
        "binding_source": _binding_source(env_ref=env_ref, vault_ref=vault_ref),
        "binding_configured": True,
        "env_value_read": False,
        "vault_value_read": False,
        "credential_material_accessed": False,
        "network_opened": False,
        "handler_executed": False,
        "external_delivery_opened": False,
        "live_production_claimed": False,
        "updated_at": str(item.get("updated_at", "")),
    }


def _find_registry_binding(
    registry: tuple[dict[str, JsonValue], ...],
    *,
    surface_kind: str,
    surface_id: str,
    credential_scope: str,
) -> Optional[dict[str, JsonValue]]:
    for item in registry:
        if _same_binding(
            item,
            surface_kind=surface_kind,
            surface_id=surface_id,
            credential_scope=credential_scope,
        ):
            return item
    return None


def _same_binding(
    item: dict[str, JsonValue],
    *,
    surface_kind: str,
    surface_id: str,
    credential_scope: str,
) -> bool:
    return (
        item.get("surface_kind") == surface_kind
        and item.get("surface_id") == surface_id
        and item.get("credential_scope") == credential_scope
    )


def _configured_binding_source(configured: Optional[dict[str, JsonValue]]) -> Optional[str]:
    if configured is None:
        return None
    return str(configured["binding_source"])


def _configured_env_ref(configured: Optional[dict[str, JsonValue]], *, default: str) -> str:
    if configured is None or configured.get("env_ref") is None:
        return default
    return str(configured["env_ref"])


def _configured_vault_ref(configured: Optional[dict[str, JsonValue]], *, default: str) -> str:
    if configured is None or configured.get("vault_ref") is None:
        return default
    return str(configured["vault_ref"])


def _binding_result(
    *,
    decision: str,
    binding: Optional[dict[str, JsonValue]],
    blocked_reasons: tuple[str, ...],
    redacted_input: Optional[str],
    registry_available: bool,
) -> CredentialBindingResult:
    result = CredentialBindingResult(
        decision=decision,
        binding=binding,
        blocked_reasons=blocked_reasons,
        redacted_input=redacted_input,
        binding_registry_available=registry_available,
        env_value_read=False,
        vault_value_read=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo_binding(result)})


def _no_secret_echo(result: CredentialReadinessResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)


def _no_secret_echo_binding(result: CredentialBindingResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
