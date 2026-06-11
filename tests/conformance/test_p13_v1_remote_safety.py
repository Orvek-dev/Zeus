"""P13 conformance — /v1 remote safety.

/v1 is spoken by vanilla LLM SDKs (static headers only), so it can't be
HMAC-paired like /zeus — a static token is the ceiling. A non-loopback bind
refuses to start without auth; when auth is on, the token's registration (not
spoofable x-zeus-* headers) decides identity, and a missing token is a 401.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli_main import app
from zeus_agent.decision_api_runtime import HostKind, ZeusDecisionEngine
from zeus_agent.governor_runtime import GovernorBank
from zeus_agent.pairing_runtime import PairingManager
from zeus_agent.proxy_runtime import (
    LlmProxyEngine,
    make_proxy_handler,
    seed_proxy_capability_store,
)
from zeus_agent.trust_loop_runtime import (
    FlightRecorder,
    SQLiteApprovalQueue,
    SQLiteControlPlaneStore,
    SQLiteEvidenceLedger,
)

runner = CliRunner()


def _parts(tmp_path: Path) -> tuple[LlmProxyEngine, PairingManager, ZeusDecisionEngine]:
    store = SQLiteControlPlaneStore(tmp_path / "state.sqlite3")
    recorder = FlightRecorder(SQLiteEvidenceLedger(tmp_path / "ledger.sqlite3"))
    engine = ZeusDecisionEngine(
        recorder=recorder,
        capabilities=seed_proxy_capability_store(),
        governors=GovernorBank(budget_store=store),
        queue=SQLiteApprovalQueue(store),
        seq_counter=lambda: store.next_counter("decision_seq"),
    )
    return LlmProxyEngine(engine=engine, store=store), PairingManager(store), engine


def _handler_instance(proxy: LlmProxyEngine, pairing: PairingManager, *, required: bool):
    """A handler instance with a captured 401 sink — no socket needed to test
    the /v1 auth decision in isolation."""
    handler_cls = make_proxy_handler(
        proxy, "http://upstream.invalid", v1_token_required=required, pairing=pairing
    )
    instance = handler_cls.__new__(handler_cls)
    captured: list[tuple[int, dict]] = []
    instance._write_json = lambda status, payload: captured.append((status, payload))  # type: ignore[attr-defined]
    return instance, captured


# ------------------------------------------------------------- token lifecycle
def test_v1_token_roundtrip(tmp_path: Path) -> None:
    _proxy, pairing, _engine = _parts(tmp_path)
    issued = pairing.issue_v1_token("hermes", principal_id="agent.hermes.coord")
    token = issued["token"]
    registration = pairing.verify_v1_token(token)
    assert registration is not None
    assert registration["host"] == "hermes"
    assert registration["principal"] == "agent.hermes.coord"
    assert pairing.verify_v1_token("zv1_not_a_real_token") is None
    assert pairing.verify_v1_token(None) is None
    assert pairing.verify_v1_token("") is None


def test_v1_token_expiry_and_revoke(tmp_path: Path) -> None:
    _proxy, pairing, _engine = _parts(tmp_path)
    issued = pairing.issue_v1_token("hermes", ttl_days=7)
    token = issued["token"]
    assert issued["expires_at"] != "never"

    # valid now, but rejected once past its expiry (fail-closed)
    assert pairing.verify_v1_token(token) is not None
    future = datetime.now(timezone.utc) + timedelta(days=8)
    assert pairing.verify_v1_token(token, now=future) is None

    # revoke kills it immediately
    fresh = pairing.issue_v1_token("hermes", ttl_days=0)["token"]  # never-expiring
    assert pairing.verify_v1_token(fresh) is not None
    assert pairing.revoke_v1_token(fresh) is True
    assert pairing.verify_v1_token(fresh) is None
    assert pairing.revoke_v1_token("zv1_unknown") is False


# ------------------------------------------- non-loopback bind refuses w/o auth
def test_nonloopback_bind_refuses_without_token(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["proxy", "--bind", "0.0.0.0", "--upstream", "http://up", "--home", str(tmp_path / "zeus")],
    )
    assert result.exit_code != 0
    assert "--require-v1-auth" in result.output or "--require-v1-auth" in str(result.exception)


# ------------------------------------------------------ missing token is a 401
def test_v1_guard_rejects_missing_token(tmp_path: Path) -> None:
    proxy, pairing, engine = _parts(tmp_path)
    instance, captured = _handler_instance(proxy, pairing, required=True)
    instance.headers = {"x-zeus-principal": "agent.whoever"}  # type: ignore[attr-defined]

    assert instance._v1_session() is None  # type: ignore[attr-defined]
    assert captured and captured[0][0] == 401
    assert captured[0][1]["error"]["code"] == "v1_token_required"
    # the refusal is evidence
    denies = [
        r
        for r in engine.recorder.ledger.records()
        if str(r["kind"]) == "decision_receipt"
    ]
    assert any("v1_token_required" in str(r["payload_json"]) for r in denies)


# ------------------------------------ token identity overrides spoofed headers
def test_v1_token_overrides_spoofed_header(tmp_path: Path) -> None:
    proxy, pairing, _engine = _parts(tmp_path)
    token = pairing.issue_v1_token("hermes", principal_id="agent.hermes.coord")["token"]
    instance, _captured = _handler_instance(proxy, pairing, required=True)
    # the caller LIES about its principal in the header; the token must win
    instance.headers = {  # type: ignore[attr-defined]
        "x-zeus-v1-token": token,
        "x-zeus-principal": "agent.attacker",
        "x-zeus-host": "openclaw",
    }
    session = instance._v1_session()  # type: ignore[attr-defined]
    assert session is not None
    assert session.principal_id == "agent.hermes.coord"  # not agent.attacker
    assert session.host is HostKind.hermes  # not openclaw


def test_v1_unknown_registered_host_never_inherits_spoofed_header(tmp_path: Path) -> None:
    """If the token's registered host string is not a known HostKind, the host
    falls back to a NEUTRAL default — never to the spoofable x-zeus-host."""
    proxy, pairing, _engine = _parts(tmp_path)
    # "hermes-prod" is not a HostKind value
    token = pairing.issue_v1_token("hermes-prod", principal_id="agent.hermes.prod")["token"]
    instance, _captured = _handler_instance(proxy, pairing, required=True)
    instance.headers = {"x-zeus-v1-token": token, "x-zeus-host": "openclaw"}  # type: ignore[attr-defined]
    session = instance._v1_session()  # type: ignore[attr-defined]
    assert session is not None
    assert session.host is HostKind.console  # NOT openclaw from the header
    assert session.principal_id == "agent.hermes.prod"


# -------------------------------------------- loopback open path is unchanged
def test_loopback_open_returns_header_session(tmp_path: Path) -> None:
    proxy, pairing, _engine = _parts(tmp_path)
    instance, _captured = _handler_instance(proxy, pairing, required=False)
    instance.headers = {"x-zeus-principal": "agent.local", "x-zeus-host": "claude_code"}  # type: ignore[attr-defined]
    session = instance._v1_session()  # type: ignore[attr-defined]
    assert session is not None
    assert session.principal_id == "agent.local"
    assert session.host is HostKind.claude_code
