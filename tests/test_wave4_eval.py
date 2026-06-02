from __future__ import annotations

from zeus_agent.eval.wave4 import run_wave4_eval


def test_wave4_eval_reports_deterministic_named_pass_counts() -> None:
    expected_names = [
        "connector_lifecycle",
        "credential_policy",
        "workflow_identity",
        "gateway_drafts",
        "observability",
        "upstream_compatibility",
    ]
    report = run_wave4_eval()
    assert report["suite"] == "wave4"
    assert report["total"] == 6
    assert report["passed"] == 6
    assert report["failed"] == 0
    assert [check["name"] for check in report["checks"]] == expected_names
    assert [check["status"] for check in report["checks"]] == ["pass"] * 6
