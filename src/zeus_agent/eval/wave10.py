from __future__ import annotations

from typing import Union

from zeus_agent.wave10_provider_scenarios import (
    Wave10Payload,
    wave10_provider_blocks_payload,
    wave10_provider_happy_payload,
)

Wave10EvalValue = Union[int, str, list[dict[str, str]]]
Wave10EvalPayload = dict[str, Wave10EvalValue]


def run_wave10_eval() -> Wave10EvalPayload:
    happy = wave10_provider_happy_payload()
    blocked = wave10_provider_blocks_payload(raw_secret="sk-wave10-eval-secret")
    checks = [
        _check("provider_contract_compiled", happy["provider_contract_compiled"] is True),
        _check("provider_routes", _provider_routes_pass(happy)),
        _check("provider_metadata", _provider_metadata_pass(happy)),
        _check("runtime_lease_usage_fallback", _lease_usage_fallback_pass(happy)),
        _check("happy_side_effects_closed", _happy_side_effects_pass(happy)),
        _check("block_labels", _block_labels_pass(blocked)),
        _check("blocked_side_effects_closed", _blocked_side_effects_pass(blocked)),
        _check("no_secret_echo", _no_secret_echo_pass(happy, blocked)),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave10",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _provider_routes_pass(payload: Wave10Payload) -> bool:
    return (
        payload["fake_provider"] == "selected"
        and payload["local_llm_provider"] == "selected"
        and payload["openai_compatible_provider"] == "dry_run"
        and payload["anthropic_metadata_provider"] == "dry_run"
    )


def _provider_metadata_pass(payload: Wave10Payload) -> bool:
    return (
        payload["openai_arguments_json"] is True
        and payload["tool_call_id_recorded"] is True
        and payload["anthropic_tool_use_metadata"] is True
        and payload["local_endpoint_metadata"] is True
    )


def _lease_usage_fallback_pass(payload: Wave10Payload) -> bool:
    return (
        payload["usage_budget_recorded"] is True
        and payload["fallback_route_recorded"] is True
        and payload["runtime_lease_validated"] is True
    )


def _happy_side_effects_pass(payload: Wave10Payload) -> bool:
    return (
        payload["handler_executed"] is False
        and payload["network_opened"] is False
        and payload["sdk_imported"] is False
        and payload["credential_material_accessed"] is False
    )


def _block_labels_pass(payload: Wave10Payload) -> bool:
    return (
        payload["missing_runtime_lease"] == "blocked"
        and payload["malformed_runtime_lease"] == "blocked"
        and payload["expired_runtime_lease"] == "blocked"
        and payload["runtime_kind_capability_mismatch"] == "blocked"
        and payload["missing_credential_scope"] == "blocked"
        and payload["unsafe_credential"] == "blocked"
        and payload["live_network_without_scope"] == "blocked"
        and payload["metadata_authority_bypass"] == "blocked"
        and payload["fallback_after_block"] == "blocked"
        and payload["unknown_provider"] == "blocked"
        and payload["malformed_tool_arguments"] == "blocked"
        and payload["over_budget"] == "blocked"
    )


def _blocked_side_effects_pass(payload: Wave10Payload) -> bool:
    return (
        payload["handler_executed"] is False
        and payload["adapter_invoked"] is False
        and payload["client_constructed"] is False
        and payload["network_opened"] is False
        and payload["sdk_imported"] is False
        and payload["credential_material_accessed"] is False
    )


def _no_secret_echo_pass(happy: Wave10Payload, blocked: Wave10Payload) -> bool:
    return (
        happy["no_secret_echo"] is True
        and blocked["no_secret_echo"] is True
        and blocked["raw_secret_present"] is False
    )
