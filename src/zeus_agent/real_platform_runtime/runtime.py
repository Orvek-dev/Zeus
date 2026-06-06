from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final, Optional

from zeus_agent.acp_runtime import handle_acp_message
from zeus_agent.batch_runtime import run_objective_batch
from zeus_agent.gateway_runtime.api import GatewayApiRuntime
from zeus_agent.gateway_runtime.models import GatewaySessionCreateRequest
from zeus_agent.gateway_runtime.security import GatewaySecurityRequestContext
from zeus_agent.real_platform_runtime.models import RealPlatformContract
from zeus_agent.real_platform_runtime.models import RealPlatformDecision
from zeus_agent.real_platform_runtime.models import RealPlatformScenario
from zeus_agent.session_runtime import SessionStore

_TARGET_VERSION: Final = "v1.3.0"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.3.0.gateway_api_session_platform"
_SUPPORTED_SCENARIOS: Final[frozenset[str]] = frozenset(
    {
        "status",
        "api-dry-run",
        "gateway-loopback-smoke",
        "gateway-blocked-external",
        "session-secret-boundary",
        "batch-acp-smoke",
    },
)
_API_ROUTES: Final[tuple[str, ...]] = (
    "/health",
    "/v1/health",
    "/v1/capabilities",
    "/v1/models",
    "/v1/chat/completions",
    "/v1/responses",
    "/v1/runs",
)
_GATEWAY_TOKEN: Final = "v130-loopback-token"


def build_real_platform_contract(
    *,
    scenario: str = "status",
    home: Optional[Path] = None,
) -> RealPlatformContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in _SUPPORTED_SCENARIOS:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_real_platform_scenario",),
        )
    parsed_scenario = _parse_scenario(safe_scenario)
    if parsed_scenario in {"gateway-loopback-smoke", "gateway-blocked-external", "session-secret-boundary"}:
        return _with_temp_home(parsed_scenario, home=home)
    return _build(parsed_scenario, home=home, cleanup_performed=False)


def _with_temp_home(scenario: RealPlatformScenario, *, home: Optional[Path]) -> RealPlatformContract:
    if home is not None:
        return _build(scenario, home=home, cleanup_performed=False)
    with tempfile.TemporaryDirectory(prefix="zeus-v130-platform-") as raw_home:
        result = _build(scenario, home=Path(raw_home), cleanup_performed=False)
    return result.model_copy(update={"cleanup_performed": True}).with_secret_scan()


def _build(
    scenario: RealPlatformScenario,
    *,
    home: Optional[Path],
    cleanup_performed: bool,
) -> RealPlatformContract:
    if scenario == "status":
        return _contract(decision="report", scenario="status", cleanup_performed=cleanup_performed)
    if scenario == "api-dry-run":
        return _api_dry_run(cleanup_performed=cleanup_performed)
    if scenario == "gateway-loopback-smoke":
        return _gateway_loopback_smoke(_required_home(home), cleanup_performed=cleanup_performed)
    if scenario == "gateway-blocked-external":
        return _gateway_blocked_external(_required_home(home), cleanup_performed=cleanup_performed)
    if scenario == "session-secret-boundary":
        return _session_secret_boundary(_required_home(home), cleanup_performed=cleanup_performed)
    return _batch_acp_smoke(cleanup_performed=cleanup_performed)


def _api_dry_run(*, cleanup_performed: bool) -> RealPlatformContract:
    return _contract(
        decision="report",
        scenario="api-dry-run",
        api_dry_run_ready=True,
        api_routes=_API_ROUTES,
        cleanup_performed=cleanup_performed,
    )


def _gateway_loopback_smoke(home: Path, *, cleanup_performed: bool) -> RealPlatformContract:
    runtime = GatewayApiRuntime(db_path=home / "gateway.sqlite3")
    request = GatewaySessionCreateRequest(
        session_id="v130.session",
        run_id="v130.run",
        goal_contract_id="v130.goal",
        resume_token="v130-resume-token",
        message="governed gateway loopback smoke",
    )
    security = _gateway_security(method="POST", path="/v1/gateway/sessions")
    first = runtime.create_session(request, security, idempotency_key="v130.idem")
    replay = runtime.create_session(request, security, idempotency_key="v130.idem")
    audit = runtime.audit_summary(_gateway_security(method="GET", path="/v1/gateway/audit"))
    return _contract(
        decision="report",
        scenario="gateway-loopback-smoke",
        gateway_loopback_ready=first.decision == "allowed" and replay.idempotency_replay_stable,
        gateway_decision=first.decision,
        gateway_reason=first.reason,
        gateway_session_count=audit.gateway_session_count,
        gateway_audit_records=audit.audit_records,
        idempotency_replay_stable=replay.idempotency_replay_stable,
        cleanup_performed=cleanup_performed,
    )


def _gateway_blocked_external(home: Path, *, cleanup_performed: bool) -> RealPlatformContract:
    runtime = GatewayApiRuntime(db_path=home / "gateway.sqlite3")
    blocked = runtime.blocked_surface(_gateway_security(method="POST", path="/v1/gateway/external-delivery"))
    return _contract(
        decision="blocked",
        scenario="gateway-blocked-external",
        blocked_reasons=(blocked.reason,),
        gateway_decision=blocked.decision,
        gateway_reason=blocked.reason,
        gateway_audit_records=blocked.audit_records,
        cleanup_performed=cleanup_performed,
    )


def _session_secret_boundary(home: Path, *, cleanup_performed: bool) -> RealPlatformContract:
    store = SessionStore(home / "session-store")
    session = store.ensure_session(
        session_id="v130-local-session",
        profile="chat",
        provider_id="fake",
        title="v1.3.0 session smoke",
    )
    store.append_message(session_id=session.session_id, role="user", content="api_key=abc123")
    exported = store.export_json(session.session_id)
    return _contract(
        decision="report",
        scenario="session-secret-boundary",
        session_store_ready=True,
        session_export_ready="api_key=abc123" not in exported.lower(),
        session_message_count=len(store.messages(session.session_id)),
        raw_secret_returned="api_key=abc123" in exported.lower(),
        cleanup_performed=cleanup_performed,
    )


def _batch_acp_smoke(*, cleanup_performed: bool) -> RealPlatformContract:
    batch = run_objective_batch(
        batch_id="v130.batch",
        objectives=("Summarize Zeus platform status", "Open unrestricted external gateway"),
    )
    acp = handle_acp_message(
        {
            "jsonrpc": "2.0",
            "id": "v130-acp",
            "method": "zeus.objective.compile",
            "params": {"objective": "Summarize Zeus ACP platform contract"},
        },
    )
    result = acp.get("result")
    return _contract(
        decision="report",
        scenario="batch-acp-smoke",
        batch_runner_ready=True,
        acp_adapter_ready=isinstance(result, dict),
        batch_compiled_count=int(batch["compiled_count"]),
        batch_blocked_count=int(batch["blocked_count"]),
        acp_method="zeus.objective.compile",
        cleanup_performed=cleanup_performed,
    )


def _contract(
    *,
    decision: RealPlatformDecision,
    scenario: RealPlatformScenario,
    blocked_reasons: tuple[str, ...] = (),
    api_dry_run_ready: bool = False,
    gateway_loopback_ready: bool = False,
    session_store_ready: bool = False,
    session_export_ready: bool = False,
    batch_runner_ready: bool = False,
    acp_adapter_ready: bool = False,
    api_routes: tuple[str, ...] = (),
    gateway_decision: Optional[str] = None,
    gateway_reason: Optional[str] = None,
    gateway_session_count: int = 0,
    gateway_audit_records: int = 0,
    idempotency_replay_stable: bool = False,
    session_message_count: int = 0,
    batch_compiled_count: int = 0,
    batch_blocked_count: int = 0,
    acp_method: Optional[str] = None,
    raw_secret_returned: bool = False,
    cleanup_performed: bool = False,
) -> RealPlatformContract:
    return RealPlatformContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        release_stage="gateway_api_session_platform",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        api_dry_run_ready=api_dry_run_ready,
        gateway_loopback_ready=gateway_loopback_ready,
        session_store_ready=session_store_ready,
        session_export_ready=session_export_ready,
        batch_runner_ready=batch_runner_ready,
        acp_adapter_ready=acp_adapter_ready,
        real_platform_runtime_ready=any(
            (api_dry_run_ready, gateway_loopback_ready, session_export_ready, batch_runner_ready and acp_adapter_ready),
        ),
        production_ready=False,
        api_routes=api_routes,
        gateway_decision=gateway_decision,
        gateway_reason=gateway_reason,
        gateway_session_count=gateway_session_count,
        gateway_audit_records=gateway_audit_records,
        idempotency_replay_stable=idempotency_replay_stable,
        session_message_count=session_message_count,
        batch_compiled_count=batch_compiled_count,
        batch_blocked_count=batch_blocked_count,
        acp_method=acp_method,
        server_started=False,
        handler_executed=False,
        network_opened=False,
        external_delivery_opened=False,
        credential_material_accessed=False,
        raw_secret_returned=raw_secret_returned,
        cleanup_performed=cleanup_performed,
        live_production_claimed=False,
    ).with_secret_scan()


def _gateway_security(*, method: str, path: str) -> GatewaySecurityRequestContext:
    return GatewaySecurityRequestContext(
        method=method,
        path=path,
        host="127.0.0.1",
        client_host="127.0.0.1",
        authorization_header="Bearer {0}".format(_GATEWAY_TOKEN),
        expected_token=_GATEWAY_TOKEN,
    )


def _required_home(home: Optional[Path]) -> Path:
    if home is None:
        raise ValueError("home_required")
    return home


def _parse_scenario(value: str) -> RealPlatformScenario:
    if value == "status":
        return "status"
    if value == "api-dry-run":
        return "api-dry-run"
    if value == "gateway-loopback-smoke":
        return "gateway-loopback-smoke"
    if value == "gateway-blocked-external":
        return "gateway-blocked-external"
    if value == "session-secret-boundary":
        return "session-secret-boundary"
    return "batch-acp-smoke"
