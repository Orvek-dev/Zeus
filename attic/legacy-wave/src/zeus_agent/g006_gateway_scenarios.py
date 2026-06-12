from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final, Union

from zeus_agent.gateway_runtime.api import GatewayApiRuntime
from zeus_agent.gateway_runtime.models import (
    GatewayApiResponse,
    GatewaySessionCreateRequest,
    GatewaySessionResumeRequest,
)
from zeus_agent.gateway_runtime.security import GatewaySecurityRequestContext

G006ScenarioValue = Union[bool, int, str]
G006Payload = dict[str, G006ScenarioValue]

_AUTH_TOKEN: Final = "g006-secret-auth-token"
_RESUME_TOKEN: Final = "g006-secret-resume-token"
_SESSION_ID: Final = "session-g006-001"
_RUN_ID: Final = "run-g006-001"
_GOAL_CONTRACT_ID: Final = "goal-g006-001"
_IDEMPOTENCY_KEY: Final = "idem-g006-session"


def g006_gateway_loopback_payload(
    home: Path | None = None,
    *,
    db_path: Path | None = None,
) -> G006Payload:
    with _runtime_db_path(home, db_path) as selected_db_path:
        runtime = GatewayApiRuntime(db_path=selected_db_path)
        created = runtime.create_session(
            _create_request(),
            _security(path="/gateway/session/create"),
            _IDEMPOTENCY_KEY,
        )
        resumed = runtime.resume_session(
            _SESSION_ID,
            _resume_request(),
            _security(path="/v1/gateway/sessions/{0}/resume".format(_SESSION_ID)),
        )
    serialized = _serialized(created, resumed)
    return {
        "scenario_id": "C001",
        "gateway_api_runtime_created": True,
        "session_persisted": created.session_persisted,
        "resume_succeeded": resumed.resume_succeeded,
        "session_id": resumed.session_id or "",
        "run_id": resumed.run_id or "",
        "goal_contract_id": resumed.goal_contract_id or "",
        "audit_record_created": created.audit_record_created and resumed.audit_record_created,
        "audit_records": resumed.audit_records,
        "gateway_session_count": resumed.gateway_session_count,
        "loopback_http_opened": created.loopback_http_opened or resumed.loopback_http_opened,
        "external_delivery_opened": _any_external_delivery_opened(created, resumed),
        "webhook_registered": _any_webhook_registered(created, resumed),
        "standing_order_created": _any_standing_order_created(created, resumed),
        "no_secret_echo": _secrets_absent(serialized, _AUTH_TOKEN, _RESUME_TOKEN),
        "live_production_claimed": _any_live_production_claimed(created, resumed),
    }


def g006_gateway_idempotency_payload(
    home: Path | None = None,
    *,
    db_path: Path | None = None,
) -> G006Payload:
    with _runtime_db_path(home, db_path) as selected_db_path:
        runtime = GatewayApiRuntime(db_path=selected_db_path)
        created = runtime.create_session(_create_request(), _security(), _IDEMPOTENCY_KEY)
        replayed = runtime.create_session(_create_request(), _security(), _IDEMPOTENCY_KEY)
        conflict = runtime.create_session(
            _create_request(
                session_id="session-g006-002",
                message="changed gateway session",
            ),
            _security(),
            _IDEMPOTENCY_KEY,
        )
    serialized = _serialized(created, replayed, conflict)
    return {
        "scenario_id": "C002",
        "idempotency_replay_stable": _same_identity(created, replayed)
        and replayed.idempotency_replay_stable,
        "replay_audit_records": replayed.audit_records,
        "conflict_reason": conflict.reason,
        "conflict_status_code": conflict.status_code,
        "gateway_session_count": conflict.gateway_session_count,
        "side_effect_count": _side_effect_count(created, replayed, conflict),
        "handler_executed": _any_handler_executed(created, replayed, conflict),
        "external_delivery_opened": _any_external_delivery_opened(created, replayed, conflict),
        "webhook_registered": _any_webhook_registered(created, replayed, conflict),
        "standing_order_created": _any_standing_order_created(created, replayed, conflict),
        "no_secret_echo": _secrets_absent(serialized, _AUTH_TOKEN, _RESUME_TOKEN),
        "live_production_claimed": _any_live_production_claimed(created, replayed, conflict),
    }


def g006_gateway_fail_closed_payload(
    raw_secret: str,
    home: Path | None = None,
    *,
    db_path: Path | None = None,
) -> G006Payload:
    with _runtime_db_path(home, db_path) as selected_db_path:
        runtime = GatewayApiRuntime(db_path=selected_db_path)
        unauthenticated = runtime.create_session(
            _create_request(
                session_id="session-g006-blocked-auth",
                message="blocked unauthenticated gateway session",
            ),
            _security(authorization_header=None, expected_token=raw_secret),
            "idem-g006-blocked-auth",
        )
        non_loopback = runtime.create_session(
            _create_request(
                session_id="session-g006-blocked-host",
                message="blocked non loopback gateway session",
            ),
            _security(
                host="api.example.test",
                authorization_header="Bearer {0}".format(raw_secret),
                expected_token=raw_secret,
            ),
            "idem-g006-blocked-host",
        )
        webhook = runtime.blocked_surface(_raw_secret_security("/gateway/webhook/session", raw_secret))
        external_delivery = runtime.blocked_surface(
            _raw_secret_security("/gateway/external-delivery/send", raw_secret),
        )
        standing_order = runtime.blocked_surface(
            _raw_secret_security("/gateway/standing-order/create", raw_secret),
        )
    blocked = (unauthenticated, non_loopback, webhook, external_delivery, standing_order)
    serialized = _serialized(*blocked)
    return {
        "scenario_id": "C003",
        "unauthenticated": unauthenticated.reason,
        "non_loopback_host": non_loopback.reason,
        "webhook": webhook.reason,
        "external_delivery": external_delivery.reason,
        "standing_order": standing_order.reason,
        "handler_executed": _any_handler_executed(*blocked),
        "external_delivery_opened": _any_external_delivery_opened(*blocked),
        "webhook_registered": _any_webhook_registered(*blocked),
        "standing_order_created": _any_standing_order_created(*blocked),
        "raw_secret_present": raw_secret in serialized,
        "no_secret_echo": _secrets_absent(serialized, raw_secret),
        "live_production_claimed": _any_live_production_claimed(*blocked),
    }


@contextmanager
def _runtime_db_path(home: Path | None, db_path: Path | None) -> Iterator[Path]:
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        yield db_path
        return
    if home is not None:
        home.mkdir(parents=True, exist_ok=True)
        yield home / "gateway.sqlite"
        return
    with tempfile.TemporaryDirectory(prefix="zeus-g006-gateway-") as raw_home:
        yield Path(raw_home) / "gateway.sqlite"


def _create_request(
    *,
    session_id: str = _SESSION_ID,
    message: str = "start gateway session",
) -> GatewaySessionCreateRequest:
    return GatewaySessionCreateRequest(
        session_id=session_id,
        run_id=_RUN_ID,
        goal_contract_id=_GOAL_CONTRACT_ID,
        resume_token=_RESUME_TOKEN,
        message=message,
    )


def _resume_request() -> GatewaySessionResumeRequest:
    return GatewaySessionResumeRequest(
        resume_token=_RESUME_TOKEN,
        message="resume gateway session",
    )


def _security(
    *,
    path: str = "/gateway/session/create",
    host: str = "127.0.0.1",
    authorization_header: str | None = "Bearer g006-secret-auth-token",
    expected_token: str = _AUTH_TOKEN,
) -> GatewaySecurityRequestContext:
    return GatewaySecurityRequestContext(
        method="POST",
        path=path,
        host=host,
        client_host="127.0.0.1",
        authorization_header=authorization_header,
        expected_token=expected_token,
    )


def _raw_secret_security(path: str, raw_secret: str) -> GatewaySecurityRequestContext:
    return _security(
        path=path,
        authorization_header="Bearer {0}".format(raw_secret),
        expected_token=raw_secret,
    )


def _serialized(*responses: GatewayApiResponse) -> str:
    return json.dumps(
        [response.model_dump(mode="json") for response in responses],
        sort_keys=True,
    )


def _secrets_absent(serialized: str, *secrets: str) -> bool:
    return all(secret not in serialized for secret in secrets)


def _same_identity(left: GatewayApiResponse, right: GatewayApiResponse) -> bool:
    return (
        left.session_id == right.session_id
        and left.run_id == right.run_id
        and left.goal_contract_id == right.goal_contract_id
    )


def _side_effect_count(*responses: GatewayApiResponse) -> int:
    return sum(response.side_effect_count for response in responses)


def _any_handler_executed(*responses: GatewayApiResponse) -> bool:
    return any(response.handler_executed for response in responses)


def _any_external_delivery_opened(*responses: GatewayApiResponse) -> bool:
    return any(response.external_delivery_opened for response in responses)


def _any_webhook_registered(*responses: GatewayApiResponse) -> bool:
    return any(response.webhook_registered for response in responses)


def _any_standing_order_created(*responses: GatewayApiResponse) -> bool:
    return any(response.standing_order_created for response in responses)


def _any_live_production_claimed(*responses: GatewayApiResponse) -> bool:
    return any(response.live_production_claimed for response in responses)
