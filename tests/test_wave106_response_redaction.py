from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditRuntime
from tests.test_wave105_transport_audit import _provider_execution


def test_response_redaction_blocks_without_audit() -> None:
    result = LiveResponseRedactionRuntime().redact(
        audit=None,
        response_payload={"content": "safe"},
        response_ref="live-response://wave106/missing",
    )

    assert result.decision == "blocked"
    assert "transport_audit_required" in result.blocked_reasons
    assert result.redacted_response is None
    assert result.live_transport_enabled is False
    assert result.network_opened is False
    assert result.live_production_claimed is False


def test_response_redaction_scrubs_secret_like_content(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    raw_secret = "sk-" + "wave106-secret"

    result = LiveResponseRedactionRuntime().redact(
        audit=_provider_audit(),
        response_payload={
            "content": "token={0}".format(raw_secret),
            "nested": {"authorization": "Bearer {0}".format(raw_secret)},
        },
        response_ref="live-response://wave106/provider",
    )

    serialized = json.dumps(result.to_payload(), sort_keys=True)
    assert result.decision == "redacted"
    assert result.audit_result_bound is True
    assert result.response_bound is True
    assert result.redaction_applied is True
    assert result.no_secret_echo is True
    assert raw_secret not in serialized
    assert "token=" not in serialized.lower()
    assert result.live_transport_enabled is False
    assert result.network_opened is False


def test_response_redaction_allows_safe_payload_without_mutation(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")

    result = LiveResponseRedactionRuntime().redact(
        audit=_provider_audit(),
        response_payload={"content": "safe loopback response", "tokens": 3},
        response_ref="live-response://wave106/provider-safe",
    )

    assert result.decision == "redacted"
    assert result.redaction_applied is False
    assert result.redacted_response == {"content": "safe loopback response", "tokens": 3}
    assert result.no_secret_echo is True


def test_response_redaction_blocks_unready_audit(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    audit = _provider_audit().model_copy(
        update={"decision": "blocked", "post_execution_audit_ready": False}
    )

    result = LiveResponseRedactionRuntime().redact(
        audit=audit,
        response_payload={"content": "safe"},
        response_ref="live-response://wave106/provider",
    )

    assert result.decision == "blocked"
    assert "transport_audit_not_ready" in result.blocked_reasons
    assert result.redacted_response is None


def test_cli_and_python_library_response_redaction(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W91_OPENAI_KEY", "provider-" + "material-value")
    raw_secret = "github_pat_" + "wave106"
    audit = _provider_audit()
    runner = CliRunner()

    completed = runner.invoke(
        app,
        [
            "live-response-redact",
            "--audit-json",
            audit.model_dump_json(),
            "--response-json",
            json.dumps({"content": raw_secret}),
            "--response-ref",
            "live-response://wave106/provider",
            "--json",
        ],
    )

    assert completed.exit_code == 0, completed.stdout
    assert raw_secret not in completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "redacted"
    assert payload["redaction_applied"] is True

    library_payload = ZeusAgent().live_response_redact(
        audit.to_payload(),
        response_payload={"content": raw_secret},
        response_ref="live-response://wave106/provider",
    )
    assert library_payload["decision"] == "redacted"
    assert raw_secret not in json.dumps(library_payload, sort_keys=True)


def _provider_audit():
    return LiveTransportAuditRuntime().audit(
        adapter_kind="provider",
        execution=_provider_execution(),
        audit_ref="live-audit://wave106/provider",
    )
