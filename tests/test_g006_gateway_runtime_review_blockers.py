from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Final

import pytest
from pydantic import JsonValue, ValidationError

from zeus_agent.gateway_runtime.api import GatewayApiRuntime
from zeus_agent.gateway_runtime.models import (
    GatewayApiResponse,
    GatewaySessionCreateRequest,
)
from zeus_agent.gateway_runtime.security import GatewaySecurityRequestContext
from zeus_agent.gateway_runtime.session_store import (
    GatewaySessionFieldError,
    SQLiteGatewaySessionStore,
)

AUTH_A: Final = "g006-http-auth-token-a"
RESUME_TOKEN: Final = "g006-http-resume-token"
JsonPayload = dict[str, JsonValue]


def test_blocked_api_decisions_report_audit_created_without_side_effects(tmp_path: Path) -> None:
    # Given: a runtime can produce unauth, malformed, blocked-surface, and conflict decisions.
    runtime = GatewayApiRuntime(db_path=tmp_path / "gateway.sqlite")
    runtime.create_session(_create_request(), _security(AUTH_A), "idem-a")

    # When / Then: every blocked decision that writes audit truthfully reports it.
    _assert_blocked_audit_response(
        runtime.create_session(_create_request(), _unauthenticated_security(), "idem-unauth"),
        "unauthenticated",
        401,
    )
    _assert_blocked_audit_response(runtime.malformed_request(_security(AUTH_A)), "malformed_request", 400)
    _assert_blocked_audit_response(
        runtime.blocked_surface(_security(AUTH_A, path="/v1/gateway/webhooks/extra")),
        "webhook_blocked",
        403,
    )
    _assert_blocked_audit_response(
        runtime.create_session(_create_request(), _security(AUTH_A), "idem-b"),
        "idempotency_conflict",
        409,
    )


@pytest.mark.parametrize("field_name", ["session_id", "run_id", "goal_contract_id"])
def test_create_request_rejects_secret_like_identity_fields(field_name: str) -> None:
    # Given: a create request identity field contains a secret-shaped value.
    body = _create_body()
    body[field_name] = "sk-g006-{0}-secret".format(field_name)

    # When / Then: boundary parsing rejects it before runtime storage.
    with pytest.raises(ValidationError):
        GatewaySessionCreateRequest(**body)


@pytest.mark.parametrize("field_name", ["session_id", "run_id", "goal_contract_id", "idempotency_key"])
def test_store_rejects_secret_like_identity_and_idempotency_key_before_persistence(
    tmp_path: Path,
    field_name: str,
) -> None:
    # Given: one storage identity/idempotency field is secret-shaped.
    db_path = tmp_path / "gateway.sqlite"
    store = SQLiteGatewaySessionStore(db_path)
    kwargs = _store_create_kwargs()
    raw_secret = "sk-g006-{0}-secret".format(field_name)
    kwargs[field_name] = raw_secret

    # When: the store is asked to persist the request.
    with pytest.raises(GatewaySessionFieldError) as error:
        store.create_or_replay_session(**kwargs)

    # Then: the typed field error occurs before SQLite storage or audit.
    assert error.value.field_name == field_name
    assert raw_secret not in _sqlite_text(db_path)
    counts = store.counts()
    assert counts.sessions == 0
    assert counts.idempotency_records == 0
    assert counts.audit_records == 0


@pytest.mark.parametrize(
    ("field_name", "raw_secret"),
    [
        ("session_id", "session-ghp_abc123"),
        ("run_id", "run-github_pat_abc123"),
        ("goal_contract_id", "goal-glpat-abc123"),
        ("idempotency_key", "idem-xoxb-token"),
    ],
)
def test_store_rejects_embedded_provider_token_like_fields_before_persistence(
    tmp_path: Path,
    field_name: str,
    raw_secret: str,
) -> None:
    # Given: a gateway identity/idempotency field embeds a provider-token-like span.
    db_path = tmp_path / "gateway.sqlite"
    store = SQLiteGatewaySessionStore(db_path)
    kwargs = _store_create_kwargs()
    kwargs[field_name] = raw_secret

    # When: the store is asked to persist the request.
    with pytest.raises(GatewaySessionFieldError) as error:
        store.create_or_replay_session(**kwargs)

    # Then: rejection happens before sessions, idempotency, or audit persist the raw value.
    assert error.value.field_name == field_name
    assert raw_secret not in _sqlite_text(db_path)
    counts = store.counts()
    assert counts.sessions == 0
    assert counts.idempotency_records == 0
    assert counts.audit_records == 0


@pytest.mark.parametrize(
    ("field_name", "benign_value"),
    [
        ("session_id", "session-normal-ghp"),
        ("run_id", "run-normal-github-pat"),
        ("goal_contract_id", "goal-normal-glpat"),
    ],
)
def test_create_request_allows_benign_near_provider_prefix_identity_fields(
    field_name: str,
    benign_value: str,
) -> None:
    # Given: an identity field resembles a provider token prefix without containing one.
    body = _create_body()
    body[field_name] = benign_value

    # When: the request crosses the API model boundary.
    request = GatewaySessionCreateRequest(**body)

    # Then: it is accepted as a public identifier rather than overblocked.
    assert request.model_dump()[field_name] == benign_value


@pytest.mark.parametrize(
    ("field_name", "benign_value"),
    [
        ("session_id", "session-graph_abc123"),
        ("run_id", "run-normal-github-pat"),
        ("goal_contract_id", "goal-normal-glpat"),
        ("idempotency_key", "idem-normal-xox"),
    ],
)
def test_store_allows_benign_near_provider_prefix_fields(
    tmp_path: Path,
    field_name: str,
    benign_value: str,
) -> None:
    # Given: a storage identity/idempotency field resembles a provider token prefix.
    db_path = tmp_path / "gateway.sqlite"
    store = SQLiteGatewaySessionStore(db_path)
    kwargs = _store_create_kwargs()
    kwargs[field_name] = benign_value

    # When: the store creates a session.
    created = store.create_or_replay_session(**kwargs)

    # Then: normal public identifiers persist once without triggering the secret guard.
    assert created.session_id == kwargs["session_id"]
    counts = store.counts()
    assert counts.sessions == 1
    assert counts.idempotency_records == 1
    assert counts.audit_records == 1


def test_api_rejects_secret_like_idempotency_key_as_malformed_without_raw_persistence(tmp_path: Path) -> None:
    # Given: the API receives a normal create body but a secret-shaped idempotency key.
    db_path = tmp_path / "gateway.sqlite"
    runtime = GatewayApiRuntime(db_path=db_path)
    raw_secret = "sk-g006-api-idempotency-secret"

    # When: the create request is evaluated.
    response = runtime.create_session(_create_request(), _security(AUTH_A), raw_secret)

    # Then: it fails closed as malformed and does not persist the raw key.
    _assert_blocked_audit_response(response, "malformed_request", 400)
    assert response.gateway_session_count == 0
    assert raw_secret not in _sqlite_text(db_path)


def test_resume_denial_sanitizes_secret_like_path_session_id_before_audit(tmp_path: Path) -> None:
    # Given: a URL/path-derived resume session id is secret-shaped and has no matching row.
    db_path = tmp_path / "gateway.sqlite"
    store = SQLiteGatewaySessionStore(db_path)
    raw_secret = "sk-g006-resume-secret"

    # When: resume fails closed before a persisted session can be found.
    session = store.resume_session(raw_secret, RESUME_TOKEN, "resume", authority_fingerprint="sha256:auth-a")

    # Then: the denial is audited without persisting the raw path secret.
    assert session is None
    assert store.counts().audit_records == 1
    assert raw_secret not in _sqlite_text(db_path)


def _create_request() -> GatewaySessionCreateRequest:
    return GatewaySessionCreateRequest(**_create_body())


def _create_body() -> JsonPayload:
    return {
        "session_id": "session-g006-review",
        "run_id": "run-g006-review",
        "goal_contract_id": "goal-g006-review",
        "resume_token": RESUME_TOKEN,
        "message": "create",
    }


def _store_create_kwargs() -> dict[str, str]:
    return {
        "session_id": "session-g006-store",
        "run_id": "run-g006-store",
        "goal_contract_id": "goal-g006-store",
        "resume_token": RESUME_TOKEN,
        "message": "create",
        "idempotency_key": "idem-g006-store",
        "authority_fingerprint": "sha256:auth-a",
    }


def _security(token: str, *, path: str = "/v1/gateway/sessions") -> GatewaySecurityRequestContext:
    return GatewaySecurityRequestContext(
        method="POST",
        path=path,
        host="127.0.0.1",
        client_host="127.0.0.1",
        authorization_header="Bearer {0}".format(token),
        expected_token=token,
    )


def _unauthenticated_security() -> GatewaySecurityRequestContext:
    return GatewaySecurityRequestContext(
        method="POST",
        path="/v1/gateway/sessions",
        host="127.0.0.1",
        client_host="127.0.0.1",
        authorization_header=None,
        expected_token=AUTH_A,
    )


def _assert_blocked_audit_response(
    response: GatewayApiResponse,
    expected_reason: str,
    expected_status: int,
) -> None:
    assert response.decision == "blocked"
    assert response.reason == expected_reason
    assert response.status_code == expected_status
    assert response.audit_record_created is True
    assert response.handler_executed is False
    assert response.side_effect_count == 0
    assert response.network_opened is False
    assert response.external_delivery_attempted is False
    assert response.external_delivery_opened is False
    assert response.webhook_registered is False
    assert response.standing_order_created is False
    assert response.credential_material_accessed is False


def _sqlite_text(db_path: Path) -> str:
    with sqlite3.connect(db_path) as connection:
        rows = []
        for table_name in ("gateway_sessions", "gateway_idempotency", "gateway_audit"):
            rows.extend(connection.execute("SELECT * FROM {0}".format(table_name)).fetchall())
    return "\n".join(str(row) for row in rows)
