from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, assert_never

from zeus_agent.gateway_runtime.api_support import (
    BLOCKED_GOAL_CONTRACT_ID,
    BLOCKED_RUN_ID,
    BLOCKED_SESSION_ID,
    GatewayApiRuntimeConfigError,
    excluding_allowed_reason,
    select_store,
)
from zeus_agent.gateway_runtime.models import (
    ExcludingAllowedReason,
    GatewayApiResponse,
    GatewaySessionCreateRequest,
    GatewaySessionResumeRequest,
)
from zeus_agent.gateway_runtime.security import (
    GatewaySecurityPolicy,
    GatewaySecurityRequestContext,
    gateway_authority_fingerprint,
)
from zeus_agent.gateway_runtime.session_store import (
    GatewaySession,
    GatewaySessionFieldError,
    GatewaySessionIdempotencyConflict,
    GatewaySessionStoreCounts,
    SQLiteGatewaySessionStore,
)


@dataclass(frozen=True, slots=True, init=False)
class GatewayApiRuntime:
    store: SQLiteGatewaySessionStore
    security_policy: GatewaySecurityPolicy

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        store: SQLiteGatewaySessionStore | None = None,
    ) -> None:
        object.__setattr__(self, "store", select_store(db_path, store))
        object.__setattr__(self, "security_policy", GatewaySecurityPolicy())

    def create_session(
        self,
        request: GatewaySessionCreateRequest,
        security: GatewaySecurityRequestContext,
        idempotency_key: str,
    ) -> GatewayApiResponse:
        authorized = self.security_policy.authorize_loopback(security)
        match authorized.decision:
            case "blocked":
                return self._record_blocked(
                    authorized,
                    session_id=request.session_id,
                    run_id=request.run_id,
                    goal_contract_id=request.goal_contract_id,
                    message=request.message,
                )
            case "allowed":
                pass
            case unreachable:
                assert_never(unreachable)
        try:
            session = self.store.create_or_replay_session(
                session_id=request.session_id,
                run_id=request.run_id,
                goal_contract_id=request.goal_contract_id,
                resume_token=request.resume_token,
                message=request.message,
                idempotency_key=idempotency_key,
                authority_fingerprint=gateway_authority_fingerprint(security),
            )
        except GatewaySessionFieldError:
            return self.malformed_request(security)
        except GatewaySessionIdempotencyConflict:
            return self._blocked("idempotency_conflict", 409, self.store.counts())
        return self._session_response(
            session,
            session_persisted=not session.idempotency_replay_stable,
            resume_succeeded=False,
            audit_record_created=True,
        )

    def resume_session(
        self,
        session_id: str,
        request: GatewaySessionResumeRequest,
        security: GatewaySecurityRequestContext,
    ) -> GatewayApiResponse:
        authorized = self.security_policy.authorize_loopback(security)
        match authorized.decision:
            case "blocked":
                return self._record_blocked(
                    authorized,
                    session_id=session_id,
                    run_id=BLOCKED_RUN_ID,
                    goal_contract_id=BLOCKED_GOAL_CONTRACT_ID,
                    message=request.message,
                )
            case "allowed":
                pass
            case unreachable:
                assert_never(unreachable)
        session = self.store.resume_session(
            session_id,
            request.resume_token,
            request.message,
            authority_fingerprint=gateway_authority_fingerprint(security),
        )
        if session is None:
            return self._blocked("unauthenticated", 401, self.store.counts())
        return self._session_response(
            session,
            session_persisted=False,
            resume_succeeded=True,
            audit_record_created=True,
        )

    def audit_summary(self, security: GatewaySecurityRequestContext) -> GatewayApiResponse:
        authorized = self.security_policy.authorize_loopback(security)
        match authorized.decision:
            case "blocked":
                return self._record_blocked(
                    authorized,
                    session_id=BLOCKED_SESSION_ID,
                    run_id=BLOCKED_RUN_ID,
                    goal_contract_id=BLOCKED_GOAL_CONTRACT_ID,
                    message=security.path,
                )
            case "allowed":
                counts = self.store.counts()
                return GatewayApiResponse.allowed(
                    audit_records=counts.audit_records,
                    gateway_session_count=counts.sessions,
                )
            case unreachable:
                assert_never(unreachable)

    def preflight_block(self, security: GatewaySecurityRequestContext) -> GatewayApiResponse | None:
        authorized = self.security_policy.authorize_loopback(security)
        match authorized.decision:
            case "blocked":
                return self._record_blocked(
                    authorized,
                    session_id=BLOCKED_SESSION_ID,
                    run_id=BLOCKED_RUN_ID,
                    goal_contract_id=BLOCKED_GOAL_CONTRACT_ID,
                    message=security.path,
                )
            case "allowed":
                return None
            case unreachable:
                assert_never(unreachable)

    def malformed_request(
        self,
        security: GatewaySecurityRequestContext,
        *,
        status_code: int = 400,
    ) -> GatewayApiResponse:
        denied = GatewayApiResponse.blocked(
            reason="malformed_request",
            status_code=status_code,
        )
        return self._record_blocked(
            denied,
            session_id=BLOCKED_SESSION_ID,
            run_id=BLOCKED_RUN_ID,
            goal_contract_id=BLOCKED_GOAL_CONTRACT_ID,
            message=security.path,
        )

    def blocked_surface(self, security: GatewaySecurityRequestContext) -> GatewayApiResponse:
        authorized = self.security_policy.authorize_loopback(security)
        match authorized.decision:
            case "blocked":
                return self._record_blocked(
                    authorized,
                    session_id=BLOCKED_SESSION_ID,
                    run_id=BLOCKED_RUN_ID,
                    goal_contract_id=BLOCKED_GOAL_CONTRACT_ID,
                    message=security.path,
                )
            case "allowed":
                denied = GatewayApiResponse.blocked(
                    reason="malformed_request",
                    status_code=400,
                )
                return self._record_blocked(
                    denied,
                    session_id=BLOCKED_SESSION_ID,
                    run_id=BLOCKED_RUN_ID,
                    goal_contract_id=BLOCKED_GOAL_CONTRACT_ID,
                    message=security.path,
                )
            case unreachable:
                assert_never(unreachable)

    def _record_blocked(
        self,
        response: GatewayApiResponse,
        *,
        session_id: str,
        run_id: str,
        goal_contract_id: str,
        message: str,
    ) -> GatewayApiResponse:
        reason = excluding_allowed_reason(response.reason)
        self.store.record_block(
            session_id=session_id,
            run_id=run_id,
            goal_contract_id=goal_contract_id,
            reason=reason,
            message=message,
        )
        return self._blocked(reason, response.status_code, self.store.counts())

    def _session_response(
        self,
        session: GatewaySession,
        *,
        session_persisted: bool,
        resume_succeeded: bool,
        audit_record_created: bool,
    ) -> GatewayApiResponse:
        counts = self.store.counts()
        return GatewayApiResponse.allowed(
            session_id=session.session_id,
            run_id=session.run_id,
            goal_contract_id=session.goal_contract_id,
            session_persisted=session_persisted,
            resume_succeeded=resume_succeeded,
            audit_record_created=audit_record_created,
            audit_records=counts.audit_records,
            gateway_session_count=counts.sessions,
            idempotency_replay_stable=session.idempotency_replay_stable,
        )

    def _blocked(
        self,
        reason: ExcludingAllowedReason,
        status_code: int,
        counts: GatewaySessionStoreCounts,
    ) -> GatewayApiResponse:
        return GatewayApiResponse(
            decision="blocked",
            reason=reason,
            status_code=status_code,
            audit_record_created=True,
            audit_records=counts.audit_records,
            gateway_session_count=counts.sessions,
        )


__all__: Final = (
    "GatewayApiRuntime",
    "GatewayApiRuntimeConfigError",
)
