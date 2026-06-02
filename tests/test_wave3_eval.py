from __future__ import annotations

from zeus_agent.eval.wave3 import run_wave3_eval


def test_wave3_eval_reports_deterministic_named_pass_counts() -> None:
    # Given: the Wave 3 eval harness.
    expected_names = ["broker", "adapter", "provider", "runtime", "cli_smoke"]

    # When: the eval report is generated.
    report = run_wave3_eval()

    # Then: deterministic counts and named checks cover the requested surfaces.
    assert report["suite"] == "wave3"
    assert report["total"] == 5
    assert report["passed"] == 5
    assert report["failed"] == 0
    assert [check["name"] for check in report["checks"]] == expected_names
    assert [check["status"] for check in report["checks"]] == ["pass"] * 5
