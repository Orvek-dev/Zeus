from __future__ import annotations

from zeus_agent.wave7_scenarios import (
    wave7_policy_blocks_payload,
    wave7_transport_registry_payload,
)


def run_wave7_eval() -> dict[str, object]:
    registry_payload = wave7_transport_registry_payload()
    policy_payload = wave7_policy_blocks_payload(
        raw_secret="ghp_TEST_FIXTURE"
    )
    checks = [
        _check("registry_covers_transport_kinds", _registry_kinds_pass(registry_payload)),
        _check("registry_live_transport_disabled", registry_payload["live_transport"] is False),
        _check("sandbox_probe_count", registry_payload["sandbox_probe_count"] == 4),
        _check("unhealthy_probe_recorded", _unhealthy_probe_pass(registry_payload)),
        _check("policy_blocks_fail_closed", _policy_blocks_pass(policy_payload)),
        _check("no_external_side_effects", _no_side_effects_pass(registry_payload, policy_payload)),
        _check("upstream_wave6_compatibility", _upstream_compatibility_pass()),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave7",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _registry_kinds_pass(payload: dict[str, object]) -> bool:
    return {
        manifest["kind"]
        for manifest in payload["manifests"]
    } == {"provider", "mcp", "api", "plugin"}


def _unhealthy_probe_pass(payload: dict[str, object]) -> bool:
    return payload["health"]["api.partner.fetch"] == "unhealthy"


def _policy_blocks_pass(payload: dict[str, object]) -> bool:
    return (
        payload["malformed_manifest"] == "blocked"
        and payload["duplicate_transport_id"] == "blocked"
        and payload["secret_like_credential_scope"] == "redacted"
        and payload["unhealthy_probe"] == "blocked"
        and payload["live_enablement_without_promotion"] == "blocked"
    )


def _no_side_effects_pass(
    registry_payload: dict[str, object],
    policy_payload: dict[str, object],
) -> bool:
    return (
        registry_payload["fake_local_only"] is True
        and registry_payload["no_external_side_effects"] is True
        and registry_payload["no_secret_echo"] is True
        and policy_payload["fake_local_only"] is True
        and policy_payload["no_external_side_effects"] is True
        and policy_payload["no_secret_echo"] is True
        and policy_payload["handler_executed"] is False
        and policy_payload["network_opened"] is False
    )


def _upstream_compatibility_pass() -> bool:
    from zeus_agent.eval.wave6 import run_wave6_eval

    report = run_wave6_eval()
    return report["suite"] == "wave6" and report["failed"] == 0
