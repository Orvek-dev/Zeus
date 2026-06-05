from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_mcp_request_body_runtime import LiveMcpRequestBodyRuntime
from tests.test_wave99_mcp_adapter_plan import _mcp_envelope


def test_mcp_request_body_materializes_jsonrpc_payload(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")
    envelope = _mcp_envelope()

    result = LiveMcpRequestBodyRuntime().materialize(
        mcp_envelope=envelope,
        arguments={"query": "Zeus"},
        body_ref="mcp-body://wave132/github",
    )

    assert result.decision == "materialized"
    assert result.mcp_request_body_materialized is True
    assert result.mcp_envelope_bound is True
    assert result.arguments_digest_bound is True
    assert result.body_payload["jsonrpc"] == "2.0"
    assert result.body_payload["method"] == "tools/call"
    assert result.body_payload["params"]["server_id"] == "mcp.github"
    assert result.body_payload["params"]["name"] == "repo.search"
    assert result.body_payload["params"]["arguments"]["query"] == "Zeus"
    assert result.network_opened is False
    assert result.raw_secret_returned is False
    assert result.live_production_claimed is False


def test_mcp_request_body_blocks_arguments_digest_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")
    envelope = _mcp_envelope()

    result = LiveMcpRequestBodyRuntime().materialize(
        mcp_envelope=envelope,
        arguments={"query": "Hermes"},
        body_ref="mcp-body://wave132/mismatch",
    )

    assert result.decision == "blocked"
    assert "arguments_digest_mismatch" in result.blocked_reasons
    assert result.mcp_request_body_materialized is False
    assert result.network_opened is False


def test_mcp_request_body_redacts_secret_like_arguments(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")
    arguments = {"query": "token=s" + "k-wave132"}
    envelope = _mcp_envelope().model_copy(update={"arguments_digest": _digest_for_test(arguments)})

    result = LiveMcpRequestBodyRuntime().materialize(
        mcp_envelope=envelope,
        arguments=arguments,
        body_ref="mcp-body://wave132/redacted",
    )

    payload = json.dumps(result.to_payload())
    assert result.decision == "materialized"
    assert "s" + "k-wave132" not in payload
    assert result.no_secret_echo is True


def test_cli_and_python_library_mcp_request_body(monkeypatch) -> None:
    monkeypatch.setenv("ZEUS_W93_GITHUB_TOKEN", "mcp-" + "material-value")
    envelope = _mcp_envelope()

    completed = CliRunner().invoke(
        app,
        [
            "live-mcp-request-body",
            "--mcp-envelope-json",
            envelope.model_dump_json(),
            "--arguments-json",
            json.dumps({"query": "Zeus"}),
            "--body-ref",
            "mcp-body://wave132/github",
            "--json",
        ],
    )
    library_payload = ZeusAgent().live_mcp_request_body(
        envelope.to_payload(),
        arguments={"query": "Zeus"},
        body_ref="mcp-body://wave132/library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "materialized"
    assert payload["body_payload"]["params"]["name"] == "repo.search"
    assert library_payload["decision"] == "materialized"


def _digest_for_test(arguments: dict[str, object]) -> str:
    import hashlib

    from zeus_agent.security.credentials import redact_secret_spans

    safe_payload = {
        redact_secret_spans(str(key)): redact_secret_spans(value) if isinstance(value, str) else value
        for key, value in arguments.items()
    }
    encoded = json.dumps(safe_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]
