from __future__ import annotations

import json
from typing import Union

from zeus_agent.model_runtime.provider_registry import ProviderRegistry
from zeus_agent.wave16_provider_http_server import Wave16ProviderHttpServer
from zeus_agent.wave16_provider_live_support import (
    all_have_metadata,
    all_metadata_true,
    block_label,
    lease,
    local_request,
    no_secret_echo,
    openai_request,
    openai_url,
)

Wave16Payload = dict[str, Union[bool, int, str]]


def wave16_provider_live_payload(scenario: str = "loopback") -> Wave16Payload:
    if scenario != "loopback":
        return {"scenario_id": "C001", "scenario_supported": False}
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        runtime_lease = lease(network_hosts=("127.0.0.1",))
        registry = ProviderRegistry()
        openai = registry.generate(
            openai_request(
                "{0}/v1/chat/completions".format(server.base_url),
                "127.0.0.1",
            ),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        local = registry.generate(
            local_request("{0}/api/generate".format(server.base_url), "127.0.0.1"),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
    finally:
        server.shutdown()
    responses = (openai, local)
    return {
        "scenario_id": "C001",
        "openai_compatible_provider": openai.decision,
        "local_llm_provider": local.decision,
        "openai_http_request_count": server.request_count("/v1/chat/completions"),
        "local_http_request_count": server.request_count("/api/generate"),
        "loopback_fake_server_started": True,
        "fake_server_shutdown": server.shutdown_complete,
        "approval_receipt_checked": all_metadata_true(responses, "approval.receipt_checked"),
        "timeout_enforced": all_metadata_true(responses, "timeout.enforced"),
        "runtime_lease_validated": all_have_metadata(responses, "lease.evidence_target"),
        "credential_scope_bound": openai.metadata_value("credential.scope_label")
        == "external.openai.readonly",
        "audit_record_created": all_metadata_true(responses, "audit.record_created"),
        "handler_executed": any(response.handler_executed for response in responses),
        "network_opened": any(response.network_opened for response in responses),
        "non_loopback_network_opened": False,
        "no_secret_echo": no_secret_echo(responses),
        "credential_material_accessed": any(
            response.credential_material_accessed for response in responses
        ),
        "sdk_imported": any(response.sdk_imported for response in responses),
        "live_production_claimed": False,
        "openai_tool_call_id_recorded": bool(openai.tool_calls)
        and openai.tool_calls[0].call_id == "call_weather_live",
    }


def wave16_provider_live_blocks_payload(raw_secret: str) -> Wave16Payload:
    server = Wave16ProviderHttpServer()
    server.start()
    try:
        runtime_lease = lease(network_hosts=("127.0.0.1", "localhost", "example.com"))
        registry = ProviderRegistry()
        missing_lease = registry.generate(openai_request(openai_url(server), "127.0.0.1"), None)
        missing_approval = registry.generate(
            openai_request(openai_url(server), "127.0.0.1", approval=False),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        missing_timeout = registry.generate(
            openai_request(openai_url(server), "127.0.0.1", timeout=False),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        live_network_required = registry.generate(
            openai_request(openai_url(server), "127.0.0.1", live_network=False),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        non_loopback = registry.generate(
            openai_request("http://example.com/v1/chat/completions", "example.com"),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        mismatch = registry.generate(
            openai_request(openai_url(server), "localhost"),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        missing_credential = registry.generate(
            openai_request(openai_url(server), "127.0.0.1", credential_scope=None),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        unsafe_credential = registry.generate(
            openai_request(openai_url(server), "127.0.0.1", credential_scope=raw_secret),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        invalid_approval = registry.generate(
            openai_request(
                openai_url(server),
                "127.0.0.1",
                approval_receipt="not-a-real-approval-receipt",
            ),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        approval_missing_capability = registry.generate(
            openai_request(
                openai_url(server),
                "127.0.0.1",
                approval_capability="provider.local.generate",
            ),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        blocked_http_request_count = server.request_count()
        malformed = registry.generate(
            openai_request("{0}/malformed".format(server.base_url), "127.0.0.1"),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        malformed_missing_id = registry.generate(
            openai_request(
                "{0}/malformed-tool-missing-id".format(server.base_url),
                "127.0.0.1",
            ),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        malformed_bad_arguments = registry.generate(
            openai_request(
                "{0}/malformed-tool-bad-arguments".format(server.base_url),
                "127.0.0.1",
            ),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
        http_status = registry.generate(
            openai_request("{0}/not-found".format(server.base_url), "127.0.0.1"),
            runtime_lease,
            now=runtime_lease.issued_at,
        )
    finally:
        server.shutdown()
    preflight = (
        missing_lease,
        missing_approval,
        missing_timeout,
        live_network_required,
        non_loopback,
        mismatch,
        missing_credential,
        unsafe_credential,
        invalid_approval,
        approval_missing_capability,
    )
    authorized_errors = (
        malformed,
        malformed_missing_id,
        malformed_bad_arguments,
        http_status,
    )
    payload: Wave16Payload = {
        "scenario_id": "C002",
        "missing_runtime_lease": block_label(missing_lease, "missing_runtime_lease"),
        "missing_approval": block_label(missing_approval, "missing_approval"),
        "missing_timeout": block_label(missing_timeout, "missing_timeout"),
        "live_network_required": block_label(live_network_required, "live_network_required"),
        "non_loopback_endpoint": block_label(non_loopback, "non_loopback_endpoint"),
        "network_host_mismatch": block_label(mismatch, "network_host_mismatch"),
        "missing_credential_scope": block_label(missing_credential, "missing_credential_scope"),
        "unsafe_credential": block_label(unsafe_credential, "unsafe_credential"),
        "invalid_approval": block_label(invalid_approval, "invalid_approval"),
        "approval_missing_capability": block_label(
            approval_missing_capability,
            "approval_missing_capability",
        ),
        "malformed_http_response": block_label(malformed, "malformed_http_response"),
        "malformed_tool_call_missing_id": block_label(
            malformed_missing_id,
            "malformed_http_response",
        ),
        "malformed_tool_call_bad_arguments": block_label(
            malformed_bad_arguments,
            "malformed_http_response",
        ),
        "http_status_error": block_label(http_status, "http_status_error"),
        "blocked_http_request_count": blocked_http_request_count,
        "malformed_http_request_count": server.request_count("/malformed"),
        "malformed_tool_call_request_count": server.request_count("/malformed-tool-missing-id")
        + server.request_count("/malformed-tool-bad-arguments"),
        "http_status_request_count": server.request_count("/not-found"),
        "http_status_network_opened": http_status.network_opened,
        "handler_executed": any(response.handler_executed for response in preflight),
        "authorized_error_handler_executed": any(
            response.handler_executed for response in authorized_errors
        ),
        "authorized_error_network_opened": all(
            response.network_opened for response in authorized_errors
        ),
        "non_loopback_network_opened": non_loopback.network_opened or mismatch.network_opened,
        "raw_secret_present": False,
        "no_secret_echo": no_secret_echo((*preflight, *authorized_errors)),
        "credential_material_accessed": any(
            response.credential_material_accessed for response in (*preflight, *authorized_errors)
        ),
        "sdk_imported": any(response.sdk_imported for response in (*preflight, *authorized_errors)),
        "live_production_claimed": False,
        "fake_server_shutdown": server.shutdown_complete,
    }
    return payload | {"raw_secret_present": raw_secret in json.dumps(payload, sort_keys=True)}
