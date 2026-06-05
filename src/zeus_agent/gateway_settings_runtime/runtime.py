from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.gateway_pairing_runtime import GatewayPairingRuntime
from zeus_agent.gateway_runtime import GatewayAdapterSpec, default_gateway_adapter_specs
from zeus_agent.security.credentials import redact_secret_spans

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
_UNSAFE_REF_MARKERS: Final[tuple[str, ...]] = (
    "ignore previous",
    "ignore system",
    "override system",
    "reveal prompt",
    "jailbreak",
)


class GatewaySettingsResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: str
    configured_target_count: int
    configured_targets: tuple[dict[str, JsonValue], ...]
    selected_target: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    config_path: str
    target_allowlist_written: bool = False
    delivery_target_allowlist_required: bool = True
    auth_configured: bool = False
    gateway_paired: bool = False
    external_delivery_opened: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class GatewaySettingsRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.config_path = home / "gateway-config.json"

    def add(self, *, adapter_ref: str, target: str) -> GatewaySettingsResult:
        clean_adapter_ref = adapter_ref.strip()
        clean_target = target.strip()
        redacted_ref = redact_secret_spans(clean_adapter_ref)
        redacted_target = redact_secret_spans(clean_target)
        if redacted_ref != clean_adapter_ref or redacted_target != clean_target:
            return self._blocked("unsafe_credential_material_detected")
        if redacted_ref == "":
            return self._blocked("empty_gateway_ref")
        if redacted_target == "":
            return self._blocked("empty_gateway_target")
        if _unsafe_ref(redacted_ref) or _unsafe_ref(redacted_target):
            return self._blocked("unsafe_gateway_ref")

        adapter = _find_adapter(redacted_ref)
        if adapter is None:
            return self._blocked("unknown_gateway_adapter")

        configured = [
            item
            for item in self._configured_targets()
            if item["adapter_id"] != adapter.adapter_id or item["target"] != redacted_target
        ]
        selected = _target_payload(
            adapter,
            target=redacted_target,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        configured.append(selected)
        self.home.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps({"targets": configured}, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return _result(
            config_path=self.config_path,
            decision="configured",
            configured_targets=tuple(configured),
            selected_target=selected,
            target_allowlist_written=True,
        )

    def list(self) -> GatewaySettingsResult:
        configured = tuple(self._configured_targets())
        return _result(
            config_path=self.config_path,
            decision="report",
            configured_targets=configured,
        )

    def _configured_targets(self) -> list[dict[str, JsonValue]]:
        if not self.config_path.exists():
            return []
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(payload, dict):
            return []
        targets = payload.get("targets", [])
        if not isinstance(targets, list):
            return []
        result: list[dict[str, JsonValue]] = []
        for item in targets:
            if isinstance(item, dict) and isinstance(item.get("adapter_id"), str) and isinstance(item.get("target"), str):
                result.append(_normalize_configured_target(item))
        return result

    def _blocked(self, reason: str) -> GatewaySettingsResult:
        return _result(
            config_path=self.config_path,
            decision="blocked",
            configured_targets=tuple(self._configured_targets()),
            blocked_reasons=(reason,),
        )


def _find_adapter(adapter_ref: str) -> Optional[GatewayAdapterSpec]:
    normalized = adapter_ref.strip().casefold()
    for adapter in default_gateway_adapter_specs():
        aliases = {
            adapter.adapter_id.casefold(),
            adapter.display_name.casefold(),
        }
        if normalized in aliases:
            return adapter
    return None


def _unsafe_ref(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in _UNSAFE_REF_MARKERS)


def _target_payload(adapter: GatewayAdapterSpec, *, target: str, updated_at: str) -> dict[str, JsonValue]:
    return {
        "adapter_id": adapter.adapter_id,
        "display_name": adapter.display_name,
        "target": target,
        "state": "quarantined",
        "catalog_state": adapter.state,
        "target_allowlisted": True,
        "fake_smoke_enabled": adapter.fake_smoke_enabled,
        "auth_required": adapter.auth_required,
        "pairing_required": adapter.pairing_required,
        "pairing_configured": False,
        "delivery_target_allowlist_required": adapter.delivery_target_allowlist_required,
        "live_delivery_supported": adapter.live_delivery_supported,
        "external_delivery_opened": False,
        "network_opened": False,
        "handler_executed": False,
        "updated_at": updated_at,
    }


def _normalize_configured_target(item: dict[str, object]) -> dict[str, JsonValue]:
    return {
        "adapter_id": str(item["adapter_id"]),
        "display_name": str(item.get("display_name", item["adapter_id"])),
        "target": str(item["target"]),
        "state": str(item.get("state", "quarantined")),
        "catalog_state": str(item.get("catalog_state", "planned_wave")),
        "target_allowlisted": bool(item.get("target_allowlisted", True)),
        "fake_smoke_enabled": bool(item.get("fake_smoke_enabled", False)),
        "auth_required": bool(item.get("auth_required", True)),
        "pairing_required": bool(item.get("pairing_required", True)),
        "pairing_configured": bool(item.get("pairing_configured", False)),
        "delivery_target_allowlist_required": bool(item.get("delivery_target_allowlist_required", True)),
        "live_delivery_supported": bool(item.get("live_delivery_supported", False)),
        "external_delivery_opened": False,
        "network_opened": False,
        "handler_executed": False,
        "updated_at": str(item.get("updated_at", "")),
    }


def _result(
    *,
    config_path: Path,
    decision: str,
    configured_targets: tuple[dict[str, JsonValue], ...],
    selected_target: Optional[dict[str, JsonValue]] = None,
    blocked_reasons: tuple[str, ...] = (),
    target_allowlist_written: bool = False,
) -> GatewaySettingsResult:
    configured_targets_with_pairing = _with_pairing_state(config_path.parent, configured_targets)
    result = GatewaySettingsResult(
        decision=decision,
        configured_target_count=len(configured_targets_with_pairing),
        configured_targets=configured_targets_with_pairing,
        selected_target=selected_target,
        blocked_reasons=blocked_reasons,
        config_path=str(config_path),
        target_allowlist_written=target_allowlist_written,
        delivery_target_allowlist_required=True,
        auth_configured=False,
        gateway_paired=_gateway_paired(configured_targets_with_pairing),
        external_delivery_opened=False,
        network_opened=False,
        handler_executed=False,
        credential_material_accessed=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _with_pairing_state(
    home: Path,
    configured_targets: tuple[dict[str, JsonValue], ...],
) -> tuple[dict[str, JsonValue], ...]:
    pairing_runtime = GatewayPairingRuntime(home)
    targets = []
    for target in configured_targets:
        targets.append(
            {
                **target,
                "pairing_configured": pairing_runtime.is_paired(
                    adapter_id=str(target["adapter_id"]),
                    target=str(target["target"]),
                ),
            },
        )
    return tuple(targets)


def _gateway_paired(configured_targets: tuple[dict[str, JsonValue], ...]) -> bool:
    required_targets = [target for target in configured_targets if bool(target.get("pairing_required", True))]
    if not required_targets:
        return False
    return all(bool(target.get("pairing_configured", False)) for target in required_targets)


def _no_secret_echo(result: GatewaySettingsResult) -> bool:
    blob = result.model_dump_json().lower()
    return not any(
        marker in blob
        for marker in (
            "sk-wave",
            "ghp_",
            "github_pat_",
            "glpat-",
            "xoxb-",
            "xoxa-",
            "xoxp-",
            "token=sk",
            "password=",
            "secret=sk",
            "private_key",
            "-----begin",
        )
    )
