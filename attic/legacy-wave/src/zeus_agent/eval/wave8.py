from __future__ import annotations

import tempfile
from pathlib import Path

from zeus_agent.wave8_scenarios import (
    wave8_runtime_integration_payload,
    wave8_transport_state_payload,
)


def run_wave8_eval() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="zeus-wave8-eval-") as raw_home:
        state_payload = wave8_transport_state_payload(Path(raw_home))
    runtime_payload = wave8_runtime_integration_payload(
        raw_secret="ghp_TEST_FIXTURE",
    )
    checks = [
        _check("transport_state_counts", _state_counts_pass(state_payload)),
        _check("transport_state_replay", state_payload["idempotency_replay_stable"] is True),
        _check("provider_registry_gate", runtime_payload["healthy_provider_allowed"] is True),
        _check("connector_registry_gate", runtime_payload["healthy_connector_allowed"] is True),
        _check("policy_blocks", _policy_blocks_pass(runtime_payload)),
        _check("no_external_side_effects", _side_effects_pass(state_payload, runtime_payload)),
        _check("no_secret_echo", _secret_pass(state_payload, runtime_payload)),
        _check("adjacent_surface_still_works", _adjacent_surface_pass()),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave8",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "adjacent_surface_still_works": _adjacent_surface_pass(),
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _state_counts_pass(payload: dict[str, object]) -> bool:
    return (
        payload["transport_manifest_count"] == 4
        and payload["transport_probe_count"] == 4
        and payload["evidence_link_count"] == 8
        and payload["live_transport"] is False
    )


def _policy_blocks_pass(payload: dict[str, object]) -> bool:
    return (
        payload["unknown_transport"] == "blocked"
        and payload["unhealthy_probe"] == "blocked"
        and payload["transport_kind_mismatch"] == "blocked"
        and payload["live_transport_not_authorized"] == "blocked"
        and payload["blocked_handler_executed"] is False
        and payload["network_opened"] is False
    )


def _side_effects_pass(
    state_payload: dict[str, object],
    runtime_payload: dict[str, object],
) -> bool:
    return (
        state_payload["fake_local_only"] is True
        and state_payload["no_external_side_effects"] is True
        and runtime_payload["fake_local_only"] is True
        and runtime_payload["network_opened"] is False
    )


def _secret_pass(
    state_payload: dict[str, object],
    runtime_payload: dict[str, object],
) -> bool:
    return state_payload["no_secret_echo"] is True and runtime_payload["no_secret_echo"] is True


def _adjacent_surface_pass() -> bool:
    from zeus_agent.eval.wave5 import run_wave5_eval
    from zeus_agent.eval.wave6 import run_wave6_eval
    from zeus_agent.eval.wave7 import run_wave7_eval

    wave5 = run_wave5_eval()
    wave6 = run_wave6_eval()
    wave7 = run_wave7_eval()
    return wave5["failed"] == 0 and wave6["failed"] == 0 and wave7["failed"] == 0
