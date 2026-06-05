from __future__ import annotations

import json

from zeus_agent.rc_closeout_runtime import build_rc_smoke_eval


def test_rc_smoke_eval_aggregates_required_suites() -> None:
    result = build_rc_smoke_eval()

    assert result.decision == "report"
    assert result.suite == "w205_w212_rc_smoke"
    assert result.total >= 12
    assert result.passed == result.total
    assert result.failed == 0
    assert result.missing_suite_count == 0
    assert "wave20_observability" in result.required_suite_ids
    assert "plugin_quarantine" in result.required_suite_ids
    assert "workflow_ulw" in result.required_suite_ids
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_rc_smoke_eval_blocks_missing_or_failed_suite() -> None:
    result = build_rc_smoke_eval(excluded_suite_ids=("wave20_observability",))

    assert result.decision == "blocked"
    assert result.failed == 1
    assert result.missing_suite_count == 1
    assert result.missing_suite_ids == ("wave20_observability",)
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_rc_smoke_eval_payload_has_no_live_claim_or_secret_echo() -> None:
    result = build_rc_smoke_eval()
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "report"
    assert payload["no_secret_echo"] is True
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert "sk-wave207" not in serialized
