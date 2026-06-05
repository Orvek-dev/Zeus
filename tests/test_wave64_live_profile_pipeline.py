from __future__ import annotations

from zeus_agent.live_cockpit_runtime import LiveCockpitRuntime


def test_live_cockpit_starts_pipeline_with_surface_profile_stage() -> None:
    result = LiveCockpitRuntime().build()

    first_stage = result.activation_pipeline[0]
    assert first_stage["stage_id"] == "live_profile"
    assert first_stage["command"] == "zeus live-profile --json"
    assert "surface" in first_stage["purpose"]
    assert first_stage["execution_allowed"] is False
    assert first_stage["network_opened"] is False
    assert first_stage["live_production_claimed"] is False


def test_live_cockpit_pipeline_remains_non_executable_after_profile_expansion() -> None:
    result = LiveCockpitRuntime().build()

    assert result.activation_pipeline_count == 5
    assert all(stage["operator_review_required"] is True for stage in result.activation_pipeline)
    assert all(stage["execution_allowed"] is False for stage in result.activation_pipeline)
    assert all(stage["handler_executed"] is False for stage in result.activation_pipeline)
    assert all(stage["external_delivery_opened"] is False for stage in result.activation_pipeline)
    assert result.network_opened is False
    assert result.live_production_claimed is False
