from __future__ import annotations

from pathlib import Path

import pytest

from zeus_agent.credential_broker_runtime import (
    CredentialBrokerService,
    EnvCredentialVault,
    InMemoryCredentialVault,
    parse_secret_proof_ref,
)
from zeus_agent.trust_loop_runtime import SQLiteEvidenceLedger, TrustDecision

RUN = "run.broker.test"
REF = "secret-proof://external.github.readonly"


def _service(tmp_path: Path) -> tuple[CredentialBrokerService, InMemoryCredentialVault, SQLiteEvidenceLedger]:
    vault = InMemoryCredentialVault()
    ledger = SQLiteEvidenceLedger(tmp_path / "ledger.sqlite3")
    return CredentialBrokerService(vault, ledger), vault, ledger


def test_parse_secret_proof_ref_roundtrip() -> None:
    assert parse_secret_proof_ref(REF) == "external.github.readonly"


def test_parse_rejects_secret_like_ref() -> None:
    with pytest.raises(ValueError):
        parse_secret_proof_ref("secret-proof://sk-live-abc123")


def test_release_on_allowed_decision(tmp_path: Path) -> None:
    service, vault, ledger = _service(tmp_path)
    vault.put("external.github.readonly", "raw-material", header_name="Authorization")
    release = service.release(
        ref=REF,
        run_id=RUN,
        capability_id="vcs.push",
        network_host="api.github.com",
        approved_hosts=("api.github.com",),
        trust_decision=TrustDecision.AUTO,
        decision_record_id="trust.ev.000001",
    )
    assert release.decision == "released"
    assert release.credential is not None
    assert release.credential.reveal_for_transport() == "raw-material"
    # The receipt references the scope label, never the material.
    record = ledger.records()[-1]
    assert "raw-material" not in str(record["payload_json"])
    assert "external.github.readonly" in str(record["payload_json"])


def test_ask_decision_never_releases(tmp_path: Path) -> None:
    service, vault, _ledger = _service(tmp_path)
    vault.put("external.github.readonly", "raw-material")
    release = service.release(
        ref=REF,
        run_id=RUN,
        capability_id="vcs.push",
        network_host="api.github.com",
        approved_hosts=("api.github.com",),
        trust_decision=TrustDecision.ASK,
    )
    assert release.decision == "blocked"
    assert release.reason == "decision_not_allowed"
    assert release.credential is None


def test_unapproved_host_blocks_release(tmp_path: Path) -> None:
    service, vault, _ledger = _service(tmp_path)
    vault.put("external.github.readonly", "raw-material")
    release = service.release(
        ref=REF,
        run_id=RUN,
        capability_id="vcs.push",
        network_host="exfil.example.com",
        approved_hosts=("api.github.com",),
        trust_decision=TrustDecision.AUTO,
    )
    assert release.decision == "blocked"
    assert release.reason == "host_not_approved"


def test_missing_vault_entry_blocks(tmp_path: Path) -> None:
    service, _vault, _ledger = _service(tmp_path)
    release = service.release(
        ref=REF,
        run_id=RUN,
        capability_id="vcs.push",
        network_host="api.github.com",
        approved_hosts=("api.github.com",),
        trust_decision=TrustDecision.AUTO,
    )
    assert release.decision == "blocked"
    assert release.reason == "credential_unavailable"


def test_blocked_release_still_leaves_receipt(tmp_path: Path) -> None:
    service, _vault, ledger = _service(tmp_path)
    service.release(
        ref=REF,
        run_id=RUN,
        capability_id="vcs.push",
        network_host="api.github.com",
        approved_hosts=(),
        trust_decision=TrustDecision.AUTO,
    )
    record = ledger.records()[-1]
    assert str(record["kind"]) == "credential_release"
    assert '"material_released":false' in str(record["payload_json"]).replace(" ", "")


def test_env_vault_resolves_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZEUS_SECRET_EXTERNAL_GITHUB_READONLY", "env-material")
    entry = EnvCredentialVault().resolve("external.github.readonly")
    assert entry is not None
    assert entry.reveal() == "env-material"
    assert "env-material" not in repr(entry)


def test_env_vault_missing_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZEUS_SECRET_MISSING_SCOPE", raising=False)
    assert EnvCredentialVault().resolve("missing.scope") is None
