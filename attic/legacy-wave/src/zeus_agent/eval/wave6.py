from __future__ import annotations

import tempfile
from pathlib import Path

from zeus_agent.wave6_scenarios import (
    wave6_promotion_controls_payload,
    wave6_runtime_state_payload,
)


def run_wave6_eval() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="zeus-wave6-eval-") as raw_home:
        home = Path(raw_home)
        state_payload = wave6_runtime_state_payload(home / "state")
        promotion_payload = wave6_promotion_controls_payload(home / "promotion")
    checks = [
        _check("runtime_state_counts", _runtime_state_counts_pass(state_payload)),
        _check("runtime_evidence_links", _runtime_evidence_links_pass(state_payload)),
        _check("promotion_blocks_live_transport", _promotion_blocks_pass(promotion_payload)),
        _check("promotion_records_retry_rollback", _promotion_metadata_pass(promotion_payload)),
        _check("no_external_side_effects", _no_side_effects_pass(state_payload, promotion_payload)),
        _check("upstream_wave5_compatibility", _upstream_compatibility_pass()),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave6",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _runtime_state_counts_pass(payload: dict[str, object]) -> bool:
    counts = payload["runtime_counts"]
    return (
        counts["provider_executions"] == 1
        and counts["connector_executions"] == 1
        and counts["execution_evidence_links"] == 2
        and payload["live_transport"] is False
    )


def _runtime_evidence_links_pass(payload: dict[str, object]) -> bool:
    return (
        payload["provider_execution"]["idempotency_key"] == "idem-wave6-provider-001"
        and payload["connector_execution"]["idempotency_key"] == "idem-wave6-connector-001"
        and payload["provider_execution"]["envelope"]["transport"] == "dry_run"
        and payload["connector_execution"]["envelope"]["transport"] == "dry_run"
    )


def _promotion_blocks_pass(payload: dict[str, object]) -> bool:
    promotion = payload["promotion"]
    return (
        promotion["decision"] == "blocked"
        and promotion["reason"] == "live_transport_not_authorized"
        and promotion["handler_executed"] is False
        and promotion["network_opened"] is False
        and promotion["approval_required"] is True
    )


def _promotion_metadata_pass(payload: dict[str, object]) -> bool:
    promotion = payload["promotion"]
    return (
        promotion["retry_policy"]["max_attempts"] == 3
        and promotion["rollback_plan"]["target"] == "provider.external.generate"
        and payload["runtime_counts"]["promotion_attempts"] == 1
    )


def _no_side_effects_pass(
    state_payload: dict[str, object],
    promotion_payload: dict[str, object],
) -> bool:
    return (
        state_payload["fake_local_only"] is True
        and state_payload["no_external_side_effects"] is True
        and state_payload["no_secret_echo"] is True
        and promotion_payload["fake_local_only"] is True
        and promotion_payload["no_external_side_effects"] is True
        and promotion_payload["no_secret_echo"] is True
    )


def _upstream_compatibility_pass() -> bool:
    from zeus_agent.eval.wave5 import run_wave5_eval

    report = run_wave5_eval()
    return report["suite"] == "wave5" and report["failed"] == 0
