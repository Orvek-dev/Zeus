from __future__ import annotations

import json

from zeus_agent.rc_closeout_runtime import build_rc_live_opt_in_boundary


def test_rc_live_opt_in_boundary_maps_hermes_surfaces_to_zeus_steps() -> None:
    result = build_rc_live_opt_in_boundary()

    assert result.decision == "report"
    assert result.hermes_entrypoint_count >= 6
    assert result.surface_count >= 8
    assert result.explicit_live_opt_in_required is True
    assert result.project_mode_release_required is True
    assert result.production_live_ready is False
    assert "provider_api" in result.surface_ids
    assert "mcp_tools" in result.surface_ids
    assert "gateway_delivery" in result.surface_ids
    assert "browser_web" in result.surface_ids
    assert "terminal_sandbox" in result.surface_ids


def test_rc_live_opt_in_boundary_blocks_implicit_production_live_mode() -> None:
    result = build_rc_live_opt_in_boundary(requested_mode="production_live")

    assert result.decision == "blocked"
    assert result.explicit_live_opt_in_required is True
    assert result.production_live_ready is False
    assert "separate_project_mode_release_required" in result.blocked_reasons
    assert "production_live_claim_blocked" in result.blocked_reasons


def test_rc_live_opt_in_boundary_payload_is_secret_safe_and_side_effect_free() -> None:
    result = build_rc_live_opt_in_boundary(raw_request="connect with sk-wave209-secret")
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["network_opened"] is False
    assert payload["external_delivery_opened"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["handler_executed"] is False
    assert payload["live_production_claimed"] is False
    assert payload["no_secret_echo"] is True
    assert "sk-wave209-secret" not in serialized
