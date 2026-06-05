from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.api_runtime import make_api_handler
from zeus_agent.cli import app
from zeus_agent.doctor_runtime import doctor_report
from zeus_agent.entry_runtime import ZeusChatRuntime, entry_status_payload
from zeus_agent.model_runtime import provider_catalog_payload
from zeus_agent.model_runtime.fallback import (
    evaluate_provider_fallback,
    provider_budget_payload,
)
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.session_runtime import SessionStore
from zeus_agent.setup_runtime import setup_plan


def test_provider_catalog_exposes_hermes_grade_profiles_without_live_claim() -> None:
    payload = provider_catalog_payload()

    assert payload["provider_profile_count"] >= 15
    assert "openai_compatible" in payload["api_modes"]
    assert "anthropic_messages" in payload["api_modes"]
    assert payload["local_first_count"] >= 4
    assert payload["tool_calling_count"] >= 7
    assert payload["live_production_claimed"] is False


def test_provider_fallback_requires_equal_or_narrower_lease() -> None:
    lease = RuntimeLease(
        lease_id="wave21.lease.provider",
        objective_id="wave21.objective.provider",
        principal_id="wave21.principal.local",
        run_id="wave21.run.provider",
        allowed_capabilities=("provider.external.generate", "provider.local.generate"),
        credential_scopes=("external.openai.readonly",),
        network_hosts=("api.openai.com",),
        budget_limit=10,
        evidence_target="mneme.wave21.provider",
        live_transport_allowed=False,
    )

    blocked = evaluate_provider_fallback(
        primary_provider_id="local-llm",
        fallback_provider_id="openai",
        lease=lease,
    )
    allowed_same_external_scope = evaluate_provider_fallback(
        primary_provider_id="openai-compatible",
        fallback_provider_id="openai",
        lease=lease,
    )
    budget = provider_budget_payload(
        provider_id="openai",
        lease=lease,
        budget_required=11,
    )

    assert blocked.decision == "blocked"
    assert blocked.reason == "local_to_external_fallback_requires_live_transport"
    assert allowed_same_external_scope.decision == "allowed"
    assert budget["decision"] == "blocked"
    assert budget["reason"] == "budget_exceeded"
    assert budget["live_production_claimed"] is False


def test_chat_runtime_records_session_and_redacts_secret(tmp_path: Path) -> None:
    runtime = ZeusChatRuntime(tmp_path)
    result = runtime.run_turn(
        message="hello token=raw-secret-value",
        session_id="wave21",
        provider_id="fake",
    )
    exported = runtime.session_payload("wave21")
    serialized = json.dumps(exported, sort_keys=True)

    assert result.provider_id == "fake"
    assert result.objective_mode_active is False
    assert result.live_production_claimed is False
    assert result.raw_secret_echoed is False
    assert "raw-secret-value" not in serialized
    assert "[redacted-secret]" in serialized


def test_session_store_search_export_and_import(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    store.ensure_session(
        session_id="s1",
        profile="chat",
        provider_id="fake",
        title="Session One",
    )
    store.append_message(session_id="s1", role="user", content="Find Olympus workflow")
    exported = store.export_session("s1")

    assert store.search("Olympus")
    assert exported["raw_secret_exported"] is False

    second = SessionStore(tmp_path / "second")
    imported = second.import_session(exported)
    assert imported.session_id == "s1"
    assert second.messages("s1")


def test_setup_and_doctor_are_plan_only_and_secret_safe(tmp_path: Path) -> None:
    setup = setup_plan(
        home=tmp_path,
        provider_id="fake",
        mcp=True,
        local=True,
    )
    doctor = doctor_report(tmp_path)

    assert setup["setup_plan_created"] is True
    assert setup["mcp_setup_requested"] is True
    assert setup["raw_secret_echoed"] is False
    assert setup["live_production_claimed"] is False
    assert doctor["doctor_ok"] is True
    assert doctor["live_production_claimed"] is False
    assert any(check["id"] == "live.production.claim" and check["status"] == "blocked" for check in doctor["checks"])


def test_entry_status_counts_sessions_and_providers(tmp_path: Path) -> None:
    ZeusChatRuntime(tmp_path).run_turn(message="status please", session_id="status")
    payload = entry_status_payload(tmp_path)

    assert payload["zeus_persona"] == "active"
    assert payload["session_count"] == 1
    assert payload["provider_profile_count"] >= 15
    assert payload["live_production_claimed"] is False


def test_api_runtime_serves_health_models_chat_and_responses(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_api_handler(tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:{0}".format(server.server_address[1])
    try:
        health = _get_json(base + "/health")
        models = _get_json(base + "/v1/models")
        chat = _post_json(
            base + "/v1/chat/completions",
            {"messages": [{"role": "user", "content": "hello"}]},
        )
        response = _post_json(base + "/v1/responses", {"input": "hello"})
        fetched = _get_json(base + "/v1/responses/" + str(response["id"]))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert health["status"] == "ok"
    assert models["object"] == "list"
    assert len(models["data"]) >= 15
    assert chat["choices"][0]["message"]["content"].startswith("Zeus is here")
    assert response["status"] == "completed"
    assert fetched["id"] == response["id"]
    assert health["live_production_claimed"] is False
    assert chat["live_production_claimed"] is False


def test_cli_wave21_entry_commands_are_available(tmp_path: Path) -> None:
    runner = CliRunner()

    providers = runner.invoke(app, ["providers", "--json"])
    chat = runner.invoke(
        app,
        ["zeus-chat", "--message", "hello", "--home", str(tmp_path), "--json"],
    )
    status = runner.invoke(app, ["status", "--home", str(tmp_path), "--json"])

    assert providers.exit_code == 0, providers.stdout
    assert chat.exit_code == 0, chat.stdout
    assert status.exit_code == 0, status.stdout
    assert json.loads(providers.stdout)["provider_profile_count"] >= 15
    assert json.loads(chat.stdout)["assistant_message"].startswith("Zeus is here")
    assert json.loads(status.stdout)["session_count"] == 1


def _get_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))
