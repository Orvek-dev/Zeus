from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from zeus_agent.gateway_runtime.models import (
    GatewayApiResponse,
    GatewaySessionCreateRequest,
    GatewaySessionResumeRequest,
)
from zeus_agent.gateway_runtime.security import (
    GatewaySecurityPolicy,
    GatewaySecurityRequestContext,
)


def test_create_request_redacts_resume_token_when_serialized() -> None:
    # Given: trusted API input carrying a raw resume token at the boundary.
    raw_token = "g006-raw-resume-token"
    request = GatewaySessionCreateRequest(
        session_id="g006.session.one",
        run_id="g006.run.one",
        goal_contract_id="g006.goal.one",
        resume_token=raw_token,
        message="Resume with Authorization: Bearer {0}".format(raw_token),
    )

    # When: callers serialize the parsed request for logs or responses.
    dumped = request.safe_dump()
    serialized = request.model_dump_json()

    # Then: identity and message survive, but the raw token never echoes.
    assert request.resume_token == raw_token
    assert dumped["session_id"] == "g006.session.one"
    assert dumped["resume_token"] == "[redacted-secret]"
    assert raw_token not in serialized
    assert request.no_secret_echo() is True


def test_resume_request_redacts_resume_token_when_serialized() -> None:
    # Given: a resume request with a raw bearer-shaped token.
    raw_token = "Bearer g006-resume-token"
    request = GatewaySessionResumeRequest(
        resume_token=raw_token,
        message="Continue the existing session.",
    )

    # When: the request is dumped through the API boundary model.
    dumped = request.safe_dump()
    serialized = json.dumps(dumped, sort_keys=True)

    # Then: the model retains the token internally but never serializes it.
    assert request.resume_token == raw_token
    assert dumped["resume_token"] == "[redacted-secret]"
    assert raw_token not in serialized
    assert request.no_secret_echo() is True


def test_gateway_response_represents_allowed_and_blocked_outcomes() -> None:
    # Given: a successful session-create boundary response.
    allowed = GatewayApiResponse.allowed(
        reason="allowed",
        session_id="g006.session.one",
        run_id="g006.run.one",
        goal_contract_id="g006.goal.one",
        idempotency_replay_stable=True,
        request_count=1,
        response_count=1,
        session_persisted=True,
        loopback_http_opened=True,
        audit_record_created=True,
        audit_records=1,
        gateway_session_count=1,
        handler_executed=True,
    )

    # When: the response is serialized for API output.
    dumped = allowed.model_dump(mode="json")

    # Then: the allowed response carries identity, counts, and safety proofs.
    assert dumped["decision"] == "allowed"
    assert dumped["status_code"] == 200
    assert dumped["session_id"] == "g006.session.one"
    assert dumped["session_persisted"] is True
    assert dumped["resume_succeeded"] is False
    assert dumped["loopback_http_opened"] is True
    assert dumped["audit_record_created"] is True
    assert dumped["audit_records"] == 1
    assert dumped["gateway_session_count"] == 1
    assert dumped["idempotency_replay_stable"] is True
    assert dumped["idempotent_replay"] is True
    assert dumped["request_count"] == 1
    assert dumped["response_count"] == 1
    assert dumped["side_effect_count"] == 0
    assert dumped["handler_executed"] is True
    assert dumped["external_delivery_opened"] is False
    assert dumped["webhook_registered"] is False
    assert dumped["standing_order_created"] is False
    assert dumped["no_secret_echo"] is True
    assert dumped["live_production_claimed"] is False

    # When: a malformed body is represented as a blocked API response.
    blocked = GatewayApiResponse.blocked(reason="malformed_request", status_code=400)

    # Then: the blocked response is fail-closed and handler-free.
    assert blocked.decision == "blocked"
    assert blocked.reason == "malformed_request"
    assert blocked.status_code == 400
    assert blocked.handler_executed is False
    assert blocked.session_persisted is False
    assert blocked.resume_succeeded is False
    assert blocked.loopback_http_opened is False
    assert blocked.audit_record_created is False
    assert blocked.idempotency_replay_stable is False
    assert blocked.external_delivery_opened is False
    assert blocked.webhook_registered is False
    assert blocked.standing_order_created is False
    assert blocked.live_production_claimed is False


def test_create_request_rejects_empty_body_as_malformed_boundary_input() -> None:
    # Given / When / Then: empty body text fails before gateway handling.
    with pytest.raises(ValidationError):
        GatewaySessionCreateRequest(
            session_id="g006.session.empty",
            run_id="g006.run.empty",
            goal_contract_id="g006.goal.empty",
            resume_token="g006-token",
            message=" ",
        )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/gateway/session/create"),
        ("POST", "/v1/gateway/sessions"),
        ("POST", "/v1/gateway/sessions/g006.session.one/resume"),
        ("GET", "/v1/gateway/audit"),
    ],
)
def test_security_policy_allows_authenticated_loopback_paths(method: str, path: str) -> None:
    # Given: an authenticated loopback request to an allowed gateway path.
    context = _context(method=method, path=path)

    # When: loopback authorization is evaluated.
    response = GatewaySecurityPolicy().authorize_loopback(context)

    # Then: the request is allowed without claiming handler execution.
    assert response.decision == "allowed"
    assert response.reason == "allowed"
    assert response.status_code == 200
    assert response.handler_executed is False
    assert response.no_secret_echo is True
    assert response.live_production_claimed is False


def test_security_policy_blocks_resume_path_with_extra_segments() -> None:
    # Given: an authenticated loopback resume request with a non-contract path shape.
    context = _context(path="/v1/gateway/sessions/g006.session.one/extra/resume")

    # When: loopback authorization is evaluated.
    response = GatewaySecurityPolicy().authorize_loopback(context)

    # Then: the gateway rejects the malformed path before handler execution.
    assert response.decision == "blocked"
    assert response.reason == "malformed_request"
    assert response.status_code == 400
    assert response.handler_executed is False


@pytest.mark.parametrize(
    "authorization_header",
    [None, "Bearer wrong-token"],
)
def test_security_policy_blocks_missing_or_wrong_auth(
    authorization_header: str | None,
) -> None:
    # Given: a loopback request with absent or invalid bearer auth.
    context = _context(authorization_header=authorization_header)

    # When: loopback authorization is evaluated.
    response = GatewaySecurityPolicy().authorize_loopback(context)

    # Then: authentication fails closed before handler execution.
    assert response.decision == "blocked"
    assert response.reason == "unauthenticated"
    assert response.status_code == 401
    assert response.handler_executed is False


@pytest.mark.parametrize(
    ("host", "client_host"),
    [
        ("api.example.com", "127.0.0.1"),
        ("localhost", "203.0.113.10"),
    ],
)
def test_security_policy_blocks_non_loopback_host_or_client(
    host: str,
    client_host: str,
) -> None:
    # Given: authenticated requests with non-loopback host evidence.
    context = _context(host=host, client_host=client_host)

    # When: loopback authorization is evaluated.
    response = GatewaySecurityPolicy().authorize_loopback(context)

    # Then: non-loopback traffic is blocked even with valid auth.
    assert response.decision == "blocked"
    assert response.reason == "non_loopback_blocked"
    assert response.status_code == 403
    assert response.handler_executed is False


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("/gateway/webhook/session", "webhook_blocked"),
        ("/v1/gateway/webhooks", "webhook_blocked"),
        ("/gateway/external-delivery/send", "external_delivery_blocked"),
        ("/v1/gateway/external-delivery", "external_delivery_blocked"),
        ("/gateway/standing-order/create", "standing_order_blocked"),
        ("/v1/gateway/standing-orders", "standing_order_blocked"),
    ],
)
def test_security_policy_blocks_disallowed_surfaces(
    path: str,
    reason: str,
) -> None:
    # Given: authenticated loopback traffic to blocked gateway surfaces.
    context = _context(path=path)

    # When: loopback authorization is evaluated.
    response = GatewaySecurityPolicy().authorize_loopback(context)

    # Then: blocked surfaces never execute handlers.
    assert response.decision == "blocked"
    assert response.reason == reason
    assert response.status_code == 403
    assert response.handler_executed is False
    assert response.session_persisted is False
    assert response.resume_succeeded is False
    assert response.loopback_http_opened is False
    assert response.audit_record_created is False
    assert response.idempotency_replay_stable is False
    assert response.external_delivery_opened is False
    assert response.webhook_registered is False
    assert response.standing_order_created is False


def test_security_context_and_response_never_echo_authorization_token() -> None:
    # Given: a raw bearer token in the security request context.
    raw_token = "g006-auth-token"
    context = _context(
        authorization_header="Bearer {0}".format(raw_token),
        expected_token=raw_token,
    )

    # When: the context and response are serialized.
    response = GatewaySecurityPolicy().authorize_loopback(context)
    serialized = json.dumps(
        {
            "context": context.model_dump(mode="json"),
            "response": response.model_dump(mode="json"),
        },
        sort_keys=True,
    )

    # Then: both the Authorization header and raw bearer token are redacted.
    assert response.decision == "allowed"
    assert "Bearer {0}".format(raw_token) not in serialized
    assert raw_token not in serialized
    assert context.model_dump(mode="json")["authorization_header"] == "[redacted-secret]"
    assert context.model_dump(mode="json")["expected_token"] == "[redacted-secret]"


def _context(
    *,
    method: str = "POST",
    path: str = "/gateway/session/create",
    host: str = "localhost:8765",
    client_host: str = "127.0.0.1",
    authorization_header: str | None = "Bearer g006-expected-token",
    expected_token: str = "g006-expected-token",
) -> GatewaySecurityRequestContext:
    return GatewaySecurityRequestContext(
        method=method,
        path=path,
        host=host,
        client_host=client_host,
        authorization_header=authorization_header,
        expected_token=expected_token,
    )
