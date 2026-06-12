from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent import ZeusAgent
from zeus_agent.cli import app
from zeus_agent.live_production_approval_runtime import LiveProductionApprovalRuntime
from zeus_agent.live_production_claim_runtime import LiveProductionClaimRuntime
from tests.test_wave120_live_production_approval import _approval, _mcp_bundle, _proof, _provider_bundle


def test_live_production_claim_records_approval_idempotently(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    approval = _production_approval(tmp_path, "provider")
    runtime = LiveProductionClaimRuntime()

    first = runtime.record(home=tmp_path, approval=approval, claim_ref="production-claim://wave121/provider")
    repeated = runtime.record(home=tmp_path, approval=approval, claim_ref="production-claim://wave121/provider")

    rows = (tmp_path / "live_production_claims.jsonl").read_text(encoding="utf-8").splitlines()
    assert first.decision == "production_claim_recorded"
    assert first.production_claim_recorded is True
    assert first.live_production_claimed is True
    assert first.network_opened is False
    assert first.credential_material_accessed is False
    assert repeated.duplicate is True
    assert len(rows) == 1
    assert json.loads(rows[0])["production_claim_authorized"] is True


def test_live_production_claim_accepts_mcp_without_opening_server(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W109_GITHUB_TOKEN", "mcp-" + "material-value")
    approval = _production_approval(tmp_path, "mcp")

    result = LiveProductionClaimRuntime().record(
        home=tmp_path,
        approval=approval,
        claim_ref="production-claim://wave121/mcp",
    )

    assert result.decision == "production_claim_recorded"
    assert result.adapter_kind == "mcp"
    assert result.live_production_claimed is True
    assert result.network_opened is False
    assert result.external_delivery_opened is False


def test_live_production_claim_blocks_unready_approval(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    approval = _production_approval(tmp_path, "provider").model_copy(update={"production_claim_authorized": False})

    result = LiveProductionClaimRuntime().record(
        home=tmp_path,
        approval=approval,
        claim_ref="production-claim://wave121/provider",
    )

    assert result.decision == "blocked"
    assert "production_approval_not_ready" in result.blocked_reasons
    assert result.live_production_claimed is False
    assert not (tmp_path / "live_production_claims.jsonl").exists()


def test_cli_and_python_library_live_production_claim(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZEUS_W107_OPENAI_KEY", "provider-" + "material-value")
    approval = _production_approval(tmp_path, "provider")

    completed = CliRunner().invoke(
        app,
        [
            "live-production-claim",
            "--home",
            str(tmp_path),
            "--approval-json",
            approval.model_dump_json(),
            "--claim-ref",
            "production-claim://wave121/provider",
            "--json",
        ],
    )
    library_payload = ZeusAgent(home=tmp_path).live_production_claim(
        approval=approval.to_payload(),
        claim_ref="production-claim://wave121/provider-library",
    )

    assert completed.exit_code == 0, completed.stdout
    payload = json.loads(completed.stdout)
    assert payload["decision"] == "production_claim_recorded"
    assert payload["live_production_claimed"] is True
    assert payload["network_opened"] is False
    assert library_payload["decision"] == "production_claim_recorded"


def _production_approval(tmp_path: Path, adapter_kind: str):
    bundle = _provider_bundle(tmp_path) if adapter_kind == "provider" else _mcp_bundle(tmp_path)
    return LiveProductionApprovalRuntime().approve(
        adapter_kind=adapter_kind,
        execution=bundle["execution"],
        audit=bundle["audit"],
        teardown=bundle["teardown"],
        approval_receipt=_approval(adapter_kind),
        operator_proof=_proof(adapter_kind),
        production_ref="production-approval://wave121/{0}".format(adapter_kind),
    )
