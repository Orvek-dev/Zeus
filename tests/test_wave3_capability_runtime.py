from __future__ import annotations

from pathlib import Path

import pytest

from zeus_agent.capability_runtime import SandboxPolicy, build_wave3_capability_graph, build_wave3_handlers
from zeus_agent.capability_runtime import sandbox as sandbox_module
from zeus_agent.kernel.authority import ApprovalReceipt, AuthorityContext, CapabilityGrant, PathGrant
from zeus_agent.kernel.broker import CapabilityBroker

PROFILE = "coding-agent"
WAVE3_ADAPTER_REQ = "REQ-ZEUS-WAVE3-001:S1"
WAVE3_POLICY_REQ = "REQ-ZEUS-WAVE3-002:S1"


def _authority(root: Path, capability_ids: list[str]) -> AuthorityContext:
    path_grants = [
        PathGrant(capability_id="file.read", path_prefix=str(root)),
        PathGrant(capability_id="text.search", path_prefix=str(root)),
    ]
    return AuthorityContext(
        principal_id="wave3-principal",
        run_id="wave3-run",
        goal_contract_id="wave3-goal",
        capability_grants=[CapabilityGrant(capability_id=value) for value in capability_ids],
        path_grants=path_grants,
    )


def _approval() -> ApprovalReceipt:
    return ApprovalReceipt(
        principal_id="wave3-principal",
        run_id="wave3-run",
        goal_contract_id="wave3-goal",
        approved_capabilities=["terminal.run"],
    )


def _broker(root: Path, policy: SandboxPolicy | None = None) -> CapabilityBroker:
    return CapabilityBroker(
        graph=build_wave3_capability_graph(),
        handlers=build_wave3_handlers(root, policy),
    )


def test_broker_dispatch_allows_file_read_and_text_search_inside_sandbox_root(
    tmp_path: Path,
) -> None:
    # Given: a sandbox root with readable text fixtures and read/search authority.
    root = tmp_path / "sandbox"
    root.mkdir()
    (root / "notes.txt").write_text("needle alpha\nplain beta\n", encoding="utf-8")
    (root / "nested").mkdir()
    (root / "nested" / "other.txt").write_text("needle gamma\n", encoding="utf-8")
    broker = _broker(root)
    authority = _authority(root, ["file.read", "text.search"])

    # When: file.read and text.search are dispatched through CapabilityBroker.
    read_response = broker.dispatch(
        capability_id="file.read",
        payload={"path": str(root / "notes.txt")},
        context=authority,
        profile=PROFILE,
        criterion_id=WAVE3_ADAPTER_REQ,
    )
    search_response = broker.dispatch(
        capability_id="text.search",
        payload={"path": str(root), "query": "needle"},
        context=authority,
        profile=PROFILE,
        criterion_id=WAVE3_ADAPTER_REQ,
    )

    # Then: both adapters return sandbox-scoped results and broker records pass evidence.
    assert read_response["decision"] == "allowed"
    assert read_response["result"] == {"path": "notes.txt", "content": "needle alpha\nplain beta\n"}
    assert search_response["decision"] == "allowed"
    assert search_response["result"] == {
        "query": "needle",
        "matches": [
            {"path": "nested/other.txt", "line": 1, "snippet": "needle gamma"},
            {"path": "notes.txt", "line": 1, "snippet": "needle alpha"},
        ],
    }
    assert [record.status.value for record in broker.evidence_records] == ["pass", "pass"]
    assert [record.criterion_id for record in broker.evidence_records] == [
        WAVE3_ADAPTER_REQ,
        WAVE3_ADAPTER_REQ,
    ]


def test_terminal_run_safe_command_is_hidden_without_approval(tmp_path: Path) -> None:
    # Given: terminal authority exists but no approval receipt is supplied.
    root = tmp_path / "sandbox"
    root.mkdir()
    broker = _broker(root, SandboxPolicy())
    authority = _authority(root, ["terminal.run"])

    # When: a safe command is dispatched without approval.
    response = broker.dispatch(
        capability_id="terminal.run",
        payload={"cmd": "pwd"},
        context=authority,
        profile=PROFILE,
        criterion_id=WAVE3_ADAPTER_REQ,
    )

    # Then: the broker blocks before the handler becomes model-visible.
    assert response["decision"] == "blocked"
    assert response["reason"] == "capability_not_model_visible"
    assert response["evidence"]["status"] == "blocked"


def test_terminal_run_safe_command_runs_with_authority_approval_and_policy(
    tmp_path: Path,
) -> None:
    # Given: terminal authority, an approval receipt, and a sandbox command policy.
    root = tmp_path / "sandbox"
    root.mkdir()
    broker = _broker(root, SandboxPolicy())
    authority = _authority(root, ["terminal.run"])

    # When: an allowlisted local command is dispatched through CapabilityBroker.
    response = broker.dispatch(
        capability_id="terminal.run",
        payload={"cmd": "pwd"},
        context=authority,
        profile=PROFILE,
        approval_receipts=[_approval()],
        criterion_id=WAVE3_ADAPTER_REQ,
    )

    # Then: the command runs with cwd pinned to the sandbox and pass evidence is recorded.
    assert response["decision"] == "allowed"
    assert response["result"]["decision"] == "allowed"
    assert response["result"]["stdout"].strip() == str(root)
    assert response["result"]["stderr"] == ""
    assert response["result"]["return_code"] == 0
    assert response["result"]["handler_executed"] is True
    assert response["result"]["safe_env"] is True
    assert response["evidence"]["status"] == "pass"
    assert broker.evidence_records[0].criterion_id == WAVE3_ADAPTER_REQ


def test_terminal_run_network_like_command_is_blocked_before_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: terminal authority and approval, but subprocess execution is monitored.
    root = tmp_path / "sandbox"
    root.mkdir()
    broker = _broker(root, SandboxPolicy())
    authority = _authority(root, ["terminal.run"])
    calls: list[tuple[object, object]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("network-like command must not reach subprocess")

    monkeypatch.setattr(sandbox_module.subprocess, "run", fake_run)

    # When: a network-like terminal command is dispatched.
    response = broker.dispatch(
        capability_id="terminal.run",
        payload={"cmd": "curl https://example.com"},
        context=authority,
        profile=PROFILE,
        approval_receipts=[_approval()],
        criterion_id=WAVE3_POLICY_REQ,
    )

    # Then: policy returns blocked evidence and subprocess is never called.
    assert response["decision"] == "blocked"
    assert response["reason"] == "network_command_blocked"
    assert response["result"] == {
        "decision": "blocked",
        "reason": "network_command_blocked",
        "stdout": "",
        "stderr": "",
        "return_code": None,
        "handler_executed": False,
        "safe_env": True,
    }
    assert response["evidence"]["status"] == "blocked"
    assert calls == []


def test_file_read_path_traversal_is_blocked_by_adapter_policy(tmp_path: Path) -> None:
    # Given: path authority appears to cover a traversal string but the target resolves outside root.
    root = tmp_path / "sandbox"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside secret\n", encoding="utf-8")
    traversal_path = root / ".." / "outside.txt"
    broker = _broker(root)
    authority = _authority(root, ["file.read"])

    # When: file.read receives a traversal path through the broker.
    response = broker.dispatch(
        capability_id="file.read",
        payload={"path": str(traversal_path)},
        context=authority,
        profile=PROFILE,
        criterion_id=WAVE3_POLICY_REQ,
    )

    # Then: the adapter blocks the resolved outside-root target without returning content.
    assert response["decision"] == "blocked"
    assert response["reason"] == "path_outside_sandbox"
    assert response["result"] == {
        "decision": "blocked",
        "reason": "path_outside_sandbox",
        "path": None,
        "content": None,
    }
    assert response["evidence"]["status"] == "blocked"
