from __future__ import annotations

import json

from zeus_agent.gateway_runtime.adapters import (
    gateway_adapter_catalog_payload,
    plan_gateway_adapter_delivery,
)


def test_gateway_adapter_catalog_exposes_12_dry_run_adapters_with_required_guards() -> None:
    # Given: Zeus absorbs Hermes-style gateway breadth as adapter contracts.
    payload = gateway_adapter_catalog_payload()

    # Then: adapters are inspectable but external delivery stays blocked by default.
    assert payload["adapter_count"] == 12
    assert payload["fake_smoke_adapter_count"] == 3
    assert payload["auth_required"] is True
    assert payload["pairing_required"] is True
    assert payload["delivery_target_allowlist_required"] is True
    assert payload["external_delivery_opened"] is False
    assert payload["live_production_claimed"] is False


def test_gateway_adapter_delivery_requires_allowlisted_target_and_redacts_secret() -> None:
    # Given: an adapter delivery target includes secret-like content and is not allowlisted.
    raw_secret = "sk-wave35-secret"

    # When: Zeus evaluates the dry-run delivery.
    result = plan_gateway_adapter_delivery(
        adapter_id="slack",
        target="slack://ops?token={0}".format(raw_secret),
        allowlisted_targets=("slack://engineering",),
    )
    serialized = json.dumps(result, sort_keys=True)

    # Then: delivery blocks without raw secret echo or network side effects.
    assert result["decision"] == "blocked"
    assert "delivery_target_not_allowlisted" in result["blocked_reasons"]
    assert raw_secret not in serialized
    assert result["external_delivery_opened"] is False
    assert result["network_opened"] is False
    assert result["no_secret_echo"] is True
