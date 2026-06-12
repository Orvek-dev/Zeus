from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_provider_request_body_runtime import LiveProviderRequestBodyRuntime
from zeus_agent.live_provider_request_runtime import LiveProviderRequestRuntime
from tests.test_wave107_provider_http_transport import _secret_material, _transport_lease


def test_provider_request_body_materializes_openai_compatible_payload(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    envelope = _provider_envelope_for_message("summarize local transport state")

    result = LiveProviderRequestBodyRuntime().materialize(
        provider_envelope=envelope,
        message="summarize local transport state",
        body_ref="provider-body://wave128/openai",
    )

    assert result.decision == "materialized"
    assert result.provider_request_body_materialized is True
    assert result.provider_envelope_bound is True
    assert result.message_digest_bound is True
    assert result.body_payload["model"] == "gpt-wave128"
    assert result.body_payload["messages"][0]["role"] == "user"
    assert result.body_payload["messages"][0]["content"] == "summarize local transport state"
    assert result.body_payload["stream"] is False
    assert result.network_opened is False
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False


def test_provider_request_body_blocks_message_digest_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    envelope = _provider_envelope_for_message("original user message")

    result = LiveProviderRequestBodyRuntime().materialize(
        provider_envelope=envelope,
        message="different user message",
        body_ref="provider-body://wave128/mismatch",
    )

    assert result.decision == "blocked"
    assert "message_digest_mismatch" in result.blocked_reasons
    assert result.provider_request_body_materialized is False
    assert result.network_opened is False


def test_provider_request_body_redacts_secret_like_message_spans(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    message = "summarize token=s" + "k-" + "wave128"
    envelope = _provider_envelope_for_message(message)

    result = LiveProviderRequestBodyRuntime().materialize(
        provider_envelope=envelope,
        message=message,
        body_ref="provider-body://wave128/redacted",
    )

    payload = json.dumps(result.to_payload())
    assert result.decision == "materialized"
    assert "s" + "k-" + "wave128" not in payload
    assert result.no_secret_echo is True


def test_cli_and_python_library_provider_request_body(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    envelope = _provider_envelope_for_message("summarize local transport state")

    completed = CliRunner().invoke(
        app,
        [
            "live-provider-request-body",
            "--provider-envelope-json",
            envelope.model_dump_json(),
            "--message",
            "summarize local transport state",
            "--body-ref",
            "provider-body://wave128/openai",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_provider_request_body(
        envelope.to_payload(),
        message="summarize local transport state",
        body_ref="provider-body://wave128/library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "materialized"
    assert payload["body_payload"]["model"] == "gpt-wave128"
    assert library_payload["decision"] == "materialized"


def _provider_envelope_for_message(message: str):
    return LiveProviderRequestRuntime().prepare(
        transport_lease=_transport_lease("api.openai.local"),
        secret_material=_secret_material("api.openai.local"),
        provider_kind="openai_compatible",
        model_id="gpt-wave128",
        endpoint="https://api.openai.local/v1/chat/completions",
        message=message,
    )
