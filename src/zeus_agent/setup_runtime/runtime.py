from __future__ import annotations

from pathlib import Path
from typing import Optional

from zeus_agent.gateway_settings_runtime import GatewaySettingsRuntime
from zeus_agent.mcp_settings_runtime import McpSettingsRuntime
from zeus_agent.model_settings_runtime import ModelSettingsRuntime
from zeus_agent.model_runtime.provider_catalog import provider_catalog_payload
from zeus_agent.security.credentials import redact_secret_spans


def setup_plan(
    *,
    home: Path,
    provider_id: str = "fake",
    mcp: bool = False,
    gateway: bool = False,
    gateway_adapter: Optional[str] = None,
    gateway_target: Optional[str] = None,
    local: bool = False,
) -> dict[str, object]:
    home.mkdir(parents=True, exist_ok=True)
    config_preview = {
        "home": str(home),
        "provider_id": redact_secret_spans(provider_id),
        "profile": "chat",
        "mcp_quarantined_by_default": True,
        "gateway_quarantined_by_default": True,
        "gateway_adapter": redact_secret_spans(gateway_adapter or ""),
        "gateway_target": redact_secret_spans(gateway_target or ""),
        "local_first": local,
    }
    return {
        "setup_plan_created": True,
        "config_preview": config_preview,
        "provider_catalog": provider_catalog_payload(),
        "mcp_setup_requested": mcp,
        "gateway_setup_requested": gateway or gateway_adapter is not None or gateway_target is not None,
        "raw_secret_echoed": False,
        "live_production_claimed": False,
    }


def setup_apply(
    *,
    home: Path,
    provider_id: str = "fake",
    mcp: bool = False,
    mcp_servers: tuple[str, ...] = (),
    gateway: bool = False,
    gateway_adapter: Optional[str] = None,
    gateway_target: Optional[str] = None,
    local: bool = False,
) -> dict[str, object]:
    provider_ref = "local-llm" if local and provider_id == "fake" else provider_id
    model_settings = ModelSettingsRuntime(home).set(provider_ref=provider_ref)
    gateway_runtime = GatewaySettingsRuntime(home)
    if model_settings.decision == "blocked":
        return _apply_result(
            decision="blocked",
            home=home,
            model_settings=model_settings.to_payload(),
            mcp_settings=McpSettingsRuntime(home).list().to_payload(),
            gateway_settings=gateway_runtime.list().to_payload(),
            blocked_reasons=tuple("model:{0}".format(reason) for reason in model_settings.blocked_reasons),
            settings_written=False,
        )

    mcp_runtime = McpSettingsRuntime(home)
    mcp_settings = mcp_runtime.list()
    gateway_settings = gateway_runtime.list()
    blocked_reasons: list[str] = []
    if mcp:
        requested_servers = mcp_servers or ("github",)
        for server_ref in requested_servers:
            mcp_settings = mcp_runtime.add(server_ref=server_ref)
            blocked_reasons.extend("mcp:{0}".format(reason) for reason in mcp_settings.blocked_reasons)
    if gateway or gateway_adapter is not None or gateway_target is not None:
        gateway_settings = gateway_runtime.add(
            adapter_ref=gateway_adapter or "slack",
            target=gateway_target or "",
        )
        blocked_reasons.extend("gateway:{0}".format(reason) for reason in gateway_settings.blocked_reasons)

    return _apply_result(
        decision="blocked" if blocked_reasons else "configured",
        home=home,
        model_settings=model_settings.to_payload(),
        mcp_settings=mcp_settings.to_payload(),
        gateway_settings=gateway_settings.to_payload(),
        blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
        settings_written=not blocked_reasons,
    )


def _apply_result(
    *,
    decision: str,
    home: Path,
    model_settings: dict[str, object],
    mcp_settings: dict[str, object],
    gateway_settings: dict[str, object],
    blocked_reasons: tuple[str, ...],
    settings_written: bool,
) -> dict[str, object]:
    return {
        "decision": decision,
        "home": str(home),
        "settings_written": settings_written,
        "model_settings": model_settings,
        "mcp_settings": mcp_settings,
        "gateway_settings": gateway_settings,
        "blocked_reasons": list(blocked_reasons),
        "network_opened": False,
        "credential_material_accessed": False,
        "handler_executed": False,
        "live_production_claimed": False,
    }
