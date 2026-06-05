from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_gateway_delivery_body_runtime import LiveGatewayDeliveryBodyRuntime
from tests.test_wave98_gateway_adapter_plan import _gateway_envelope


def test_gateway_delivery_body_materializes_payload(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    envelope = _gateway_envelope()

    result = LiveGatewayDeliveryBodyRuntime().materialize(
        gateway_envelope=envelope,
        message="status update",
        body_ref="gateway-body://wave130/slack",
    )

    assert result.decision == "materialized"
    assert result.gateway_delivery_body_materialized is True
    assert result.gateway_envelope_bound is True
    assert result.message_digest_bound is True
    assert result.body_payload["adapter_id"] == "slack"
    assert result.body_payload["target"] == "slack://ops"
    assert result.body_payload["message"] == "status update"
    assert result.body_payload["idempotency_key"] == "wave92-delivery-1"
    assert result.network_opened is False
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False


def test_gateway_delivery_body_blocks_message_digest_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    envelope = _gateway_envelope()

    result = LiveGatewayDeliveryBodyRuntime().materialize(
        gateway_envelope=envelope,
        message="different status update",
        body_ref="gateway-body://wave130/mismatch",
    )

    assert result.decision == "blocked"
    assert "message_digest_mismatch" in result.blocked_reasons
    assert result.gateway_delivery_body_materialized is False
    assert result.network_opened is False


def test_gateway_delivery_body_redacts_secret_like_message_spans(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    message = "status token=s" + "k-wave130"
    envelope = _gateway_envelope().model_copy(update={"message_digest": _digest_for_test(message)})

    result = LiveGatewayDeliveryBodyRuntime().materialize(
        gateway_envelope=envelope,
        message=message,
        body_ref="gateway-body://wave130/redacted",
    )

    payload = json.dumps(result.to_payload())
    assert result.decision == "materialized"
    assert "s" + "k-wave130" not in payload
    assert result.no_secret_echo is True


def test_cli_and_python_library_gateway_delivery_body(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W92_GATEWAY_TOKEN", "gateway-" + "material-value")
    envelope = _gateway_envelope()

    completed = CliRunner().invoke(
        app,
        [
            "live-gateway-delivery-body",
            "--gateway-envelope-json",
            envelope.model_dump_json(),
            "--message",
            "status update",
            "--body-ref",
            "gateway-body://wave130/slack",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_gateway_delivery_body(
        envelope.to_payload(),
        message="status update",
        body_ref="gateway-body://wave130/library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "materialized"
    assert payload["body_payload"]["target"] == "slack://ops"
    assert library_payload["decision"] == "materialized"


def _digest_for_test(message: str) -> str:
    import hashlib

    from zeus_agent.security.credentials import redact_secret_spans

    return hashlib.sha256(redact_secret_spans(message).encode("utf-8")).hexdigest()[:16]
