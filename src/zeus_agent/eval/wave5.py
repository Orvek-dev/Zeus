from __future__ import annotations

from zeus_agent.wave5_scenarios import (
    wave5_connector_payload,
    wave5_provider_payload,
)


def run_wave5_eval() -> dict[str, object]:
    provider_payload = wave5_provider_payload()
    connector_payload = wave5_connector_payload()
    checks = [
        _check("provider_contracts", _provider_contracts_pass(provider_payload)),
        _check("provider_security", _provider_security_pass(provider_payload)),
        _check("connector_execution", _connector_execution_pass(connector_payload)),
        _check("connector_blocks", _connector_blocks_pass(connector_payload)),
        _check("no_external_side_effects", _no_side_effects_pass(provider_payload, connector_payload)),
        _check("upstream_regression", _upstream_regression_pass()),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave5",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _provider_contracts_pass(payload: dict[str, object]) -> bool:
    local_route = payload["local_route"]
    external_envelope = payload["external_envelope"]
    return (
        payload["provider_kinds"] == ["fake", "local", "external"]
        and local_route["decision"] == "selected"
        and local_route["envelope"]["provider_id"] == "local-private"
        and local_route["envelope"]["local_private"] is True
        and external_envelope["decision"] == "selected"
        and external_envelope["envelope"]["credential_scope_label"]
        == "external.openai.readonly"
    )


def _provider_security_pass(payload: dict[str, object]) -> bool:
    external_blocked = payload["external_blocked"]
    secret_block = payload["secret_block"]
    return (
        external_blocked["decision"] == "blocked"
        and external_blocked["route"]["network_allowed"] is False
        and secret_block["decision"] == "blocked"
        and payload["no_secret_echo"] is True
        and payload["no_raw_env_reads"] is True
    )


def _connector_execution_pass(payload: dict[str, object]) -> bool:
    return (
        payload["mcp_execution"]["decision"] == "allowed"
        and payload["mcp_execution"]["envelope"]["connector_kind"] == "mcp"
        and payload["api_execution"]["decision"] == "allowed"
        and payload["api_execution"]["envelope"]["connector_kind"] == "api"
        and payload["plugin_execution"]["decision"] == "allowed"
        and payload["plugin_execution"]["envelope"]["connector_kind"] == "plugin"
    )


def _connector_blocks_pass(payload: dict[str, object]) -> bool:
    return (
        payload["unhealthy_block"]["decision"] == "blocked"
        and payload["unhealthy_block"]["handler_executed"] is False
        and payload["unauthorized_block"]["decision"] == "blocked"
        and payload["unauthorized_block"]["handler_executed"] is False
        and payload["secret_block"]["decision"] == "blocked"
        and payload["no_secret_echo"] is True
    )


def _no_side_effects_pass(
    provider_payload: dict[str, object],
    connector_payload: dict[str, object],
) -> bool:
    return (
        provider_payload["no_external_side_effects"] is True
        and provider_payload["local_route"]["envelope"]["side_effects"] is False
        and provider_payload["external_envelope"]["envelope"]["side_effects"] is False
        and connector_payload["no_external_side_effects"] is True
        and connector_payload["mcp_execution"]["envelope"]["side_effects"] is False
        and connector_payload["api_execution"]["envelope"]["side_effects"] is False
        and connector_payload["plugin_execution"]["envelope"]["side_effects"] is False
    )


def _upstream_regression_pass() -> bool:
    return wave5_provider_payload()["fake_local_only"] is True
