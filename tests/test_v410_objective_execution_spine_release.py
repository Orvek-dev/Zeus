from __future__ import annotations

from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status


def test_v410_release_gate_reports_objective_execution_spine_checkpoint() -> None:
    payload = build_release_gated_ulw_status(target_version="v4.1.0").to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v4.1.0"
    assert payload["release_stage"] == "objective_execution_spine"
    assert payload["objective_execution_spine_contract_available"] is True
    assert payload["objective_run_runtime_available"] is True
    assert payload["objective_run_store_available"] is True
    assert payload["objective_start_status_export_cli_available"] is True
    assert payload["completion_arbiter_bridge_available"] is True
    assert payload["objective_evidence_graph_bridge_available"] is True
    assert payload["objective_execution_spine_ready"] is True
    assert payload["production_ready"] is False
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["next_version"] is None


def test_v410_requires_objective_run_evidence_before_release() -> None:
    payload = build_release_gated_ulw_status(target_version="v4.1.0").to_payload()

    assert payload["required_checkpoint_evidence"] == [
        "objective_run_spine_manual_qa",
        "objective_start_status_export_cli_manual_qa",
        "completion_arbiter_evidence_gate_manual_qa",
        "objective_run_no_live_execution_boundary_review",
        "red_green_tests_captured",
        "manual_qa_evidence_captured",
        "independent_review_approved",
        "github_release_checkpoint_complete",
    ]


def test_v400_points_to_v410_as_next_checkpoint() -> None:
    payload = build_release_gated_ulw_status(target_version="v4.0.0").to_payload()

    assert payload["next_version"] == "v4.1.0"
