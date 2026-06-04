from __future__ import annotations

import json
from datetime import datetime, timezone

from zeus_agent.model_runtime.interfaces import (
    ProviderMessage,
    ProviderMetadataEntry,
    ProviderRuntimeRequest,
)
from zeus_agent.model_runtime.openai_compatible_provider import _parse_openai_payload
from zeus_agent.model_runtime.provider_registry import ProviderRegistry
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.wave16_provider_live_scenarios import (
    wave16_provider_live_blocks_payload,
    wave16_provider_live_payload,
)
from zeus_agent.wave16_provider_http_server import Wave16ProviderHttpServer


def test_wave16_provider_live_loopback_posts_to_fake_http_servers() -> None:
    # Given: a live-provider scenario constrained to loopback fake HTTP endpoints.
    payload = wave16_provider_live_payload()

    # When / Then: both provider kinds execute through authorized loopback HTTP.
    assert payload["scenario_id"] == "C001"
    assert payload["openai_compatible_provider"] == "selected"
    assert payload["local_llm_provider"] == "selected"
    assert payload["openai_http_request_count"] == 1
    assert payload["local_http_request_count"] == 1
    assert payload["loopback_fake_server_started"] is True
    assert payload["fake_server_shutdown"] is True
    assert payload["approval_receipt_checked"] is True
    assert payload["timeout_enforced"] is True
    assert payload["runtime_lease_validated"] is True
    assert payload["credential_scope_bound"] is True
    assert payload["audit_record_created"] is True
    assert payload["handler_executed"] is True
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is False
    assert payload["no_secret_echo"] is True
    assert payload["credential_material_accessed"] is False
    assert payload["sdk_imported"] is False
    assert payload["live_production_claimed"] is False
    assert payload["openai_tool_call_id_recorded"] is True


def test_wave16_provider_live_blocks_preflight_and_malformed_http_response() -> None:
    # Given: adversarial live-provider inputs including a secret-like fixture.
    raw_secret = "sk-wave16-fixture"
    payload = wave16_provider_live_blocks_payload(raw_secret)

    # When / Then: unsafe inputs fail closed without leaking the raw secret.
    assert payload["scenario_id"] == "C002"
    assert payload["missing_runtime_lease"] == "blocked"
    assert payload["missing_approval"] == "blocked"
    assert payload["missing_timeout"] == "blocked"
    assert payload["live_network_required"] == "blocked"
    assert payload["non_loopback_endpoint"] == "blocked"
    assert payload["network_host_mismatch"] == "blocked"
    assert payload["missing_credential_scope"] == "blocked"
    assert payload["unsafe_credential"] == "blocked"
    assert payload["invalid_approval"] == "blocked"
    assert payload["approval_missing_capability"] == "blocked"
    assert payload["malformed_http_response"] == "blocked"
    assert payload["malformed_tool_call_missing_id"] == "blocked"
    assert payload["malformed_tool_call_bad_arguments"] == "blocked"
    assert payload["http_status_error"] == "blocked"
    assert payload["blocked_http_request_count"] == 0
    assert payload["malformed_http_request_count"] == 1
    assert payload["malformed_tool_call_request_count"] == 2
    assert payload["http_status_request_count"] == 1
    assert payload["http_status_network_opened"] is True
    assert payload["handler_executed"] is False
    assert payload["authorized_error_handler_executed"] is False
    assert payload["authorized_error_network_opened"] is True
    assert payload["non_loopback_network_opened"] is False
    assert payload["raw_secret_present"] is False
    assert payload["no_secret_echo"] is True
    assert payload["credential_material_accessed"] is False
    assert payload["sdk_imported"] is False
    assert payload["live_production_claimed"] is False
    assert raw_secret not in json.dumps(payload, sort_keys=True)


def test_wave16_provider_live_blocks_invalid_self_attested_approval() -> None:
    # Given: a loopback live request with a string that is not a typed approval receipt.
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        lease = _lease()
        request = _request(
            "{0}/v1/chat/completions".format(server.base_url),
            approval_receipt="not-a-real-approval-receipt",
        )

        # When: the provider runtime evaluates the live HTTP request.
        response = ProviderRegistry().generate(request, lease, now=lease.issued_at)
    finally:
        server.shutdown()

    # Then: the request fails closed before any HTTP request is made.
    assert response.decision == "blocked"
    assert response.metadata_value("block.reason") == "invalid_approval"
    assert response.network_opened is False
    assert server.request_count("/v1/chat/completions") == 0


def test_wave16_provider_live_marks_http_status_errors_as_network_opened() -> None:
    # Given: an authorized loopback live request to a fake endpoint that returns 404.
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        lease = _lease()
        request = _request("{0}/not-found".format(server.base_url))

        # When: the request reaches the fake HTTP server and receives an error status.
        response = ProviderRegistry().generate(request, lease, now=lease.issued_at)
    finally:
        server.shutdown()

    # Then: the provider blocks but preserves that network was opened.
    assert response.decision == "blocked"
    assert response.metadata_value("block.reason") == "http_status_error"
    assert response.metadata_value("http.status_code") == 404
    assert response.network_opened is True
    assert server.request_count("/not-found") == 1


def test_wave16_openai_parser_blocks_partially_malformed_tool_calls() -> None:
    # Given: OpenAI-compatible JSON bodies with malformed tool-call entries.
    missing_call_id = _openai_payload(
        {"function": {"name": "get_weather", "arguments": "{\"location\":\"Seoul\"}"}},
    )
    bad_arguments = _openai_payload(
        {
            "id": "call_bad_arguments",
            "function": {"name": "get_weather", "arguments": "not-json"},
        },
    )

    # When / Then: both malformed bodies fail closed instead of dropping or crashing.
    assert _parse_openai_payload(missing_call_id) is None
    assert _parse_openai_payload(bad_arguments) is None


def _lease() -> RuntimeLease:
    issued_at = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
    return RuntimeLease(
        lease_id="wave16.lease.provider.live",
        objective_id="wave16.objective.provider.live",
        principal_id="wave16.principal.provider",
        run_id="wave16.run.provider.live",
        allowed_capabilities=("provider.external.generate",),
        credential_scopes=("external.openai.readonly",),
        network_hosts=("127.0.0.1",),
        budget_limit=10_000,
        evidence_target="mneme.wave16.provider.live",
        live_transport_allowed=True,
        issued_at=issued_at,
        expires_at=datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc),
    )


def _request(endpoint: str, *, approval_receipt: str | None = None) -> ProviderRuntimeRequest:
    return ProviderRuntimeRequest(
        provider_kind="openai_compatible",
        provider_id="openai.wave16.loopback",
        model_id="gpt-wave16",
        messages=(ProviderMessage(role="user", content="Call the loopback provider."),),
        credential_scope="external.openai.readonly",
        network_host="127.0.0.1",
        live_network=True,
        evidence_target="mneme.wave16.provider.live",
        metadata=(
            ProviderMetadataEntry(key="live.endpoint", value=endpoint),
            ProviderMetadataEntry(
                key="approval.receipt",
                value=approval_receipt
                or (
                    '{"principal_id":"wave16.principal.provider","run_id":"wave16.run.provider.live",'
                    '"goal_contract_id":"wave16.objective.provider.live",'
                    '"approved_capabilities":["provider.external.generate"]}'
                ),
            ),
            ProviderMetadataEntry(key="live.timeout_ms", value=2_000),
        ),
    )


def _openai_payload(tool_call: dict[str, object]) -> dict[str, object]:
    return {
        "id": "chatcmpl_wave16_loopback",
        "choices": [{"message": {"content": "openai loopback response", "tool_calls": [tool_call]}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 5, "total_tokens": 13},
    }
