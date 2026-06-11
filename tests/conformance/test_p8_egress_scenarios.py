"""P8 conformance — the egress/filesystem ring.

egress-blocks-nonapproved-host, fs-ring-blocks-out-of-scope,
key-only-at-egress, compromised-agent-cannot-reach-unapproved-host.
"""

from __future__ import annotations

import json
from pathlib import Path

from zeus_agent.adapters.claude_code_hook import ControlPlaneState
from zeus_agent.egress_runtime import (
    EgressGate,
    EgressRequest,
    EgressRing,
    StaticVault,
    build_srt_profile,
)
from zeus_agent.proxy_runtime import seed_proxy_capability_store
from zeus_agent.taint_runtime import TaintLabel

RING = EgressRing(allowed_hosts=("api.github.com",), allowed_dirs=("/work",))


def _gate(tmp_path: Path, *, vault: StaticVault | None = None) -> tuple[EgressGate, object]:
    state = ControlPlaneState(tmp_path / "zeus")
    engine = state.build_engine(capabilities=seed_proxy_capability_store())
    # the egress surface trusts the ring, not session approvals: pre-approve
    # the ring's hosts at the engine level so taint rule #2 measures the
    # private-to-unapproved-host case against the same allowlist the ring enforces.
    engine._approved_hosts = RING.allowed_hosts  # noqa: SLF001 (test wiring)
    return EgressGate(engine=engine, ring=RING, vault=vault), engine


# ------------------------------------------------ egress-blocks-nonapproved-host
def test_egress_blocks_nonapproved_host(tmp_path: Path) -> None:
    vault = StaticVault({"github": "vault-bearer-key-7F3A"})
    gate, _engine = _gate(tmp_path, vault=vault)

    blocked, headers = gate.connect(
        EgressRequest(network_host="unapproved.example", credential_ref="github")
    )
    assert blocked.allowed is False
    assert blocked.reason == "egress_host_not_allowed"
    assert headers == {}
    assert vault.resolutions == 0, "a denied egress must never touch key material"

    allowed, headers = gate.connect(
        EgressRequest(network_host="api.github.com", credential_ref="github")
    )
    assert allowed.allowed is True
    assert allowed.credential_injected is True
    assert headers["authorization"].endswith("vault-bearer-key-7F3A")


# -------------------------------------------------- fs-ring-blocks-out-of-scope
def test_fs_ring_blocks_out_of_scope(tmp_path: Path) -> None:
    gate, _engine = _gate(tmp_path)
    inside = gate.access_path(EgressRequest(path="/work/src/a.py"))
    assert inside.allowed is True

    outside = gate.access_path(EgressRequest(path="/etc/passwd"))
    assert outside.allowed is False
    assert outside.reason == "egress_path_outside_ring"
    assert outside.receipt_id is not None  # the attempt is evidence

    ssh = gate.access_path(EgressRequest(path="~/.ssh/id_ed25519"))
    assert ssh.allowed is False  # blocked dirs beat everything


# --------------------------------------------------------- key-only-at-egress
def test_key_only_at_egress_agent_never_sees_secret(tmp_path: Path) -> None:
    vault = StaticVault({"github": "vault-bearer-key-7F3A"})
    gate, _engine = _gate(tmp_path, vault=vault)
    result, headers = gate.connect(
        EgressRequest(network_host="api.github.com", credential_ref="github")
    )
    # the agent-visible result carries the FACT of injection, never the key
    agent_view = result.model_dump_json()
    assert "vault-bearer-key-7F3A" not in agent_view
    assert result.credential_injected is True
    assert "vault-bearer-key-7F3A" in headers["authorization"]  # Zeus-side only


# ------------------------------ compromised-agent-cannot-reach-unapproved-host
def test_compromised_agent_blocked_from_unapproved_host(tmp_path: Path) -> None:
    gate, engine = _gate(tmp_path)
    # a compromised agent that read private data tries to reach a new host
    engine.taint.stamp("egress.default", TaintLabel.private, "credential.read")
    result, headers = gate.connect(EgressRequest(network_host="unapproved.example"))
    assert result.allowed is False
    assert headers == {}
    # and the attempt is VISIBLE: a deny receipt + a governed gate observation
    records = engine.recorder.ledger.records()
    deny = [
        json.loads(str(r["payload_json"]))
        for r in records
        if str(r["kind"]) == "decision_receipt"
    ]
    assert any(d.get("capability_id") == "net.connect" for d in deny)
    observations = [r for r in records if str(r["kind"]) == "gate_observation"]
    assert observations, "bypass attempts must be observed, not silent"


# ------------------------------------------------------------- srt profile
def test_srt_profile_emission_matches_ring(tmp_path: Path) -> None:
    profile = build_srt_profile(RING, proxy_port=9999, agent_command=("hermes", "run"))
    assert profile["network"]["allowedDomains"] == ["api.github.com"]
    assert profile["network"]["httpProxyPort"] == 9999
    assert "/work" in profile["filesystem"]["allowedWritePaths"]
    assert any("/.ssh" in path for path in profile["filesystem"]["deniedReadPaths"])
    assert profile["agentCommand"] == ["hermes", "run"]
