from __future__ import annotations

from pathlib import Path

import pytest

from zeus_agent.gateway_runtime.api import GatewayApiRuntime
from zeus_agent.gateway_runtime.models import (
    GatewayApiResponse,
    GatewaySessionCreateRequest,
    GatewaySessionResumeRequest,
)
from zeus_agent.gateway_runtime.security import GatewaySecurityRequestContext
from zeus_agent.gateway_runtime.session_store import SQLiteGatewaySessionStore


def test_api_runtime_creates_session_after_authorized_loopback(tmp_path: Path) -> None:
    # Given: an in-process runtime with authenticated loopback create authority.
    raw_resume_token = "g006-secret-resume-token"
    raw_auth_token = "g006-secret-auth-token"
    runtime = GatewayApiRuntime(db_path=tmp_path / "gateway.sqlite")
    request = _create_request(resume_token=raw_resume_token)
    security = _security(expected_token=raw_auth_token)

    # When: the session is created through the typed API runtime.
    response = runtime.create_session(request, security, "idem-g006-session")

    # Then: the local session is persisted and no external surface opens.
    assert isinstance(response, GatewayApiResponse)
    assert response.decision == "allowed"
    assert response.reason == "allowed"
    assert response.status_code == 200
    assert response.session_id == "session-g006-001"
    assert response.run_id == "run-g006-001"
    assert response.goal_contract_id == "goal-g006-001"
    assert response.session_persisted is True
    assert response.resume_succeeded is False
    assert response.loopback_http_opened is False
    assert response.audit_record_created is True
    assert response.audit_records >= 1
    assert response.gateway_session_count == 1
    assert response.idempotency_replay_stable is False
    assert response.live_production_claimed is False
    assert response.no_secret_echo is True
    _assert_no_external_side_effects(response)
    assert raw_resume_token not in response.model_dump_json()
    assert raw_auth_token not in response.model_dump_json()


def test_api_runtime_accepts_existing_store_and_replays_idempotently(tmp_path: Path) -> None:
    # Given: a runtime composed with an existing SQLite session store.
    store = SQLiteGatewaySessionStore(tmp_path / "gateway.sqlite")
    runtime = GatewayApiRuntime(store=store)
    request = _create_request()
    security = _security()

    # When: the same idempotent request is submitted twice.
    created = runtime.create_session(request, security, "idem-g006-session")
    replayed = runtime.create_session(request, security, "idem-g006-session")

    # Then: replay returns the same local identity without duplicating sessions.
    assert created.session_id == replayed.session_id
    assert created.run_id == replayed.run_id
    assert created.goal_contract_id == replayed.goal_contract_id
    assert replayed.decision == "allowed"
    assert replayed.audit_record_created is True
    assert replayed.audit_records == 2
    assert replayed.idempotency_replay_stable is True
    assert replayed.gateway_session_count == 1
    assert store.counts().sessions == 1
    assert store.counts().idempotency_records == 1


def test_api_runtime_conflicting_idempotency_replay_blocks_without_session_mutation(
    tmp_path: Path,
) -> None:
    # Given: a persisted idempotent gateway session.
    runtime = GatewayApiRuntime(db_path=tmp_path / "gateway.sqlite")
    security = _security()
    runtime.create_session(_create_request(), security, "idem-g006-session")

    # When: the idempotency key is reused with a different fingerprint.
    conflict = runtime.create_session(
        _create_request(session_id="session-g006-002", message="changed intent"),
        security,
        "idem-g006-session",
    )

    # Then: the conflict fails closed without duplicating session state.
    assert conflict.decision == "blocked"
    assert conflict.reason == "idempotency_conflict"
    assert conflict.status_code == 409
    assert conflict.handler_executed is False
    assert conflict.gateway_session_count == 1
    assert conflict.session_persisted is False
    assert conflict.resume_succeeded is False
    _assert_no_external_side_effects(conflict)


def test_api_runtime_blocks_create_before_session_mutation_and_records_audit(
    tmp_path: Path,
) -> None:
    # Given: a non-loopback create request that must fail authority checks first.
    runtime = GatewayApiRuntime(db_path=tmp_path / "gateway.sqlite")
    request = _create_request()
    security = _security(host="api.example.com")

    # When: the runtime evaluates the create request.
    response = runtime.create_session(request, security, "idem-g006-session")

    # Then: no gateway session is created, but the block is audited locally.
    assert response.decision == "blocked"
    assert response.reason == "non_loopback_blocked"
    assert response.status_code == 403
    assert response.handler_executed is False
    assert response.gateway_session_count == 0
    assert response.audit_records == 1
    assert response.session_persisted is False
    _assert_no_external_side_effects(response)


def test_api_runtime_resumes_authorized_session_without_token_echo(tmp_path: Path) -> None:
    # Given: an existing local gateway session and matching resume token.
    raw_resume_token = "g006-secret-resume-token"
    runtime = GatewayApiRuntime(db_path=tmp_path / "gateway.sqlite")
    runtime.create_session(
        _create_request(resume_token=raw_resume_token),
        _security(),
        "idem-g006-session",
    )

    # When: the session is resumed through the typed API runtime.
    response = runtime.resume_session(
        "session-g006-001",
        _resume_request(resume_token=raw_resume_token),
        _security(path="/v1/gateway/sessions/session-g006-001/resume"),
    )

    # Then: resume succeeds against the same identity and never echoes the token.
    assert response.decision == "allowed"
    assert response.reason == "allowed"
    assert response.status_code == 200
    assert response.session_id == "session-g006-001"
    assert response.run_id == "run-g006-001"
    assert response.goal_contract_id == "goal-g006-001"
    assert response.resume_succeeded is True
    assert response.audit_record_created is True
    assert response.gateway_session_count == 1
    assert response.no_secret_echo is True
    assert raw_resume_token not in response.model_dump_json()


@pytest.mark.parametrize(
    ("path", "reason"),
    [
        ("/gateway/webhook/session", "webhook_blocked"),
        ("/gateway/external-delivery/send", "external_delivery_blocked"),
        ("/gateway/standing-order/create", "standing_order_blocked"),
    ],
)
def test_api_runtime_records_blocked_surfaces_with_exact_reasons(
    tmp_path: Path,
    path: str,
    reason: str,
) -> None:
    # Given: an authenticated loopback request to a disallowed surface.
    runtime = GatewayApiRuntime(db_path=tmp_path / "gateway.sqlite")

    # When: the generic blocked-surface runtime method evaluates the surface.
    response = runtime.blocked_surface(_security(path=path))

    # Then: the exact fail-closed reason is returned and audited without effects.
    assert response.decision == "blocked"
    assert response.reason == reason
    assert response.status_code == 403
    assert response.handler_executed is False
    assert response.gateway_session_count == 0
    assert response.audit_records == 1
    _assert_no_external_side_effects(response)


def test_api_runtime_audit_summary_is_typed_and_authorized(tmp_path: Path) -> None:
    # Given: a runtime with one accepted gateway session audit record.
    runtime = GatewayApiRuntime(db_path=tmp_path / "gateway.sqlite")
    runtime.create_session(_create_request(), _security(), "idem-g006-session")

    # When: audit summary is requested through an authorized audit context.
    response = runtime.audit_summary(_security(method="GET", path="/v1/gateway/audit"))

    # Then: the typed response reports local audit/session counts only.
    assert isinstance(response, GatewayApiResponse)
    assert response.decision == "allowed"
    assert response.reason == "allowed"
    assert response.status_code == 200
    assert response.gateway_session_count == 1
    assert response.audit_records == 1
    assert response.live_production_claimed is False
    _assert_no_external_side_effects(response)


def _create_request(
    *,
    session_id: str = "session-g006-001",
    resume_token: str = "g006-secret-resume-token",
    message: str = "start gateway session",
) -> GatewaySessionCreateRequest:
    return GatewaySessionCreateRequest(
        session_id=session_id,
        run_id="run-g006-001",
        goal_contract_id="goal-g006-001",
        resume_token=resume_token,
        message=message,
    )


def _resume_request(
    *,
    resume_token: str = "g006-secret-resume-token",
) -> GatewaySessionResumeRequest:
    return GatewaySessionResumeRequest(
        resume_token=resume_token,
        message="resume gateway session",
    )


def _security(
    *,
    method: str = "POST",
    path: str = "/gateway/session/create",
    host: str = "127.0.0.1",
    client_host: str = "127.0.0.1",
    expected_token: str = "g006-secret-auth-token",
) -> GatewaySecurityRequestContext:
    return GatewaySecurityRequestContext(
        method=method,
        path=path,
        host=host,
        client_host=client_host,
        authorization_header="Bearer {0}".format(expected_token),
        expected_token=expected_token,
    )


def _assert_no_external_side_effects(response: GatewayApiResponse) -> None:
    assert response.external_delivery_opened is False
    assert response.webhook_registered is False
    assert response.standing_order_created is False
    assert response.network_opened is False
    assert response.external_delivery_attempted is False
    assert response.credential_material_accessed is False
