from __future__ import annotations

from pathlib import Path

import pytest

from zeus_agent.capability_runtime import SandboxPolicy, build_wave3_capability_graph, build_wave3_handlers
from zeus_agent.capability_runtime import sandbox as sandbox_module
from zeus_agent.kernel.authority import ApprovalReceipt, AuthorityContext, CapabilityGrant, PathGrant
from zeus_agent.kernel.broker import CapabilityBroker

PROFILE = "coding-agent"
WAVE3_POLICY_REQ = "REQ-ZEUS-WAVE3-002:S1"


def _authority(root: Path) -> AuthorityContext:
    return AuthorityContext(
        principal_id="wave3-principal",
        run_id="wave3-run",
        goal_contract_id="wave3-goal",
        capability_grants=[CapabilityGrant(capability_id="terminal.run")],
        path_grants=[PathGrant(capability_id="file.read", path_prefix=str(root))],
    )


def _approval() -> ApprovalReceipt:
    return ApprovalReceipt(
        principal_id="wave3-principal",
        run_id="wave3-run",
        goal_contract_id="wave3-goal",
        approved_capabilities=["terminal.run"],
    )


def _broker(root: Path) -> CapabilityBroker:
    return CapabilityBroker(
        graph=build_wave3_capability_graph(),
        handlers=build_wave3_handlers(root, SandboxPolicy()),
    )


def test_terminal_run_recursive_credential_scan_is_blocked_before_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: terminal authority and a credential-looking file inside the sandbox.
    root = tmp_path / "sandbox"
    root.mkdir()
    (root / ".env").write_text("TOKEN=sk-policy-bypass-fixture\n", encoding="utf-8")
    calls: list[tuple[object, object]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("recursive credential scan must not reach subprocess")

    monkeypatch.setattr(sandbox_module.subprocess, "run", fake_run)

    # When: an approved recursive grep targets the sandbox directory.
    response = _broker(root).dispatch(
        capability_id="terminal.run",
        payload={"cmd": "grep -R TOKEN ."},
        context=_authority(root),
        profile=PROFILE,
        approval_receipts=[_approval()],
        criterion_id=WAVE3_POLICY_REQ,
    )

    # Then: sandbox policy blocks before subprocess can read credential material.
    assert response["decision"] == "blocked"
    assert response["reason"] == "recursive_grep_blocked"
    assert response["result"]["handler_executed"] is False
    assert calls == []


def test_terminal_run_recursive_grep_is_blocked_even_for_safe_named_secret_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: terminal authority and a safe-named file containing secret-like text.
    root = tmp_path / "sandbox"
    root.mkdir()
    (root / "notes.txt").write_text("TOKEN=sk-policy-bypass-fixture\n", encoding="utf-8")
    calls: list[tuple[object, object]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("recursive grep must not reach subprocess")

    monkeypatch.setattr(sandbox_module.subprocess, "run", fake_run)

    # When: an approved recursive grep targets the sandbox directory.
    response = _broker(root).dispatch(
        capability_id="terminal.run",
        payload={"cmd": "grep -R TOKEN ."},
        context=_authority(root),
        profile=PROFILE,
        approval_receipts=[_approval()],
        criterion_id=WAVE3_POLICY_REQ,
    )

    # Then: sandbox policy blocks recursive grep before reading any file.
    assert response["decision"] == "blocked"
    assert response["reason"] == "recursive_grep_blocked"
    assert response["result"]["handler_executed"] is False
    assert calls == []


def test_terminal_run_grep_dash_pattern_cannot_bypass_credential_path_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: terminal authority and a credential file matching a dash-prefixed pattern.
    root = tmp_path / "sandbox"
    root.mkdir()
    (root / ".env").write_text("-TOKEN=sk-policy-bypass-fixture\n", encoding="utf-8")
    calls: list[tuple[object, object]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("dash-pattern credential grep must not reach subprocess")

    monkeypatch.setattr(sandbox_module.subprocess, "run", fake_run)

    # When: grep uses -- before a dash-prefixed pattern and directory path.
    response = _broker(root).dispatch(
        capability_id="terminal.run",
        payload={"argv": ["grep", "-R", "--", "-TOKEN", "."]},
        context=_authority(root),
        profile=PROFILE,
        approval_receipts=[_approval()],
        criterion_id=WAVE3_POLICY_REQ,
    )

    # Then: recursive grep is blocked before subprocess execution.
    assert response["decision"] == "blocked"
    assert response["reason"] == "recursive_grep_blocked"
    assert response["result"]["handler_executed"] is False
    assert calls == []


@pytest.mark.parametrize(
    ("payload", "expected_reason"),
    [
        ({"cmd": "grep -- -TOKEN .env"}, "credential_path"),
        ({"cmd": "grep -- -TOKEN ../outside.txt"}, "path_outside_sandbox"),
        ({"cmd": "grep --file=.env notes.txt"}, "credential_path"),
        ({"cmd": "grep --file=/etc/passwd /etc/passwd"}, "path_outside_sandbox"),
        ({"cmd": "grep -f .env notes.txt"}, "credential_path"),
    ],
)
def test_terminal_run_grep_file_operands_cannot_bypass_path_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
    expected_reason: str,
) -> None:
    # Given: terminal authority and grep operands that hide credential or outside paths.
    root = tmp_path / "sandbox"
    root.mkdir()
    (root / ".env").write_text("-TOKEN=sk-policy-bypass-fixture\n", encoding="utf-8")
    (root / "notes.txt").write_text("safe note\n", encoding="utf-8")
    calls: list[tuple[object, object]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("credential or out-of-scope grep must not reach subprocess")

    monkeypatch.setattr(sandbox_module.subprocess, "run", fake_run)

    # When: an approved non-recursive grep uses pattern/file option forms.
    response = _broker(root).dispatch(
        capability_id="terminal.run",
        payload=payload,
        context=_authority(root),
        profile=PROFILE,
        approval_receipts=[_approval()],
        criterion_id=WAVE3_POLICY_REQ,
    )

    # Then: sandbox policy blocks the file-bearing operands before subprocess.
    assert response["decision"] == "blocked"
    assert response["reason"] == expected_reason
    assert response["result"]["handler_executed"] is False
    assert calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {"cmd": "grep -d recurse TOKEN ."},
        {"cmd": "grep --directories=recurse TOKEN ."},
        {"cmd": "grep --directories recurse TOKEN ."},
        {"cmd": "grep --directories skip -R TOKEN ."},
    ],
)
def test_terminal_run_grep_directory_recurse_options_are_blocked_before_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    # Given: terminal authority and alternate grep recursive directory syntax.
    root = tmp_path / "sandbox"
    root.mkdir()
    (root / ".env").write_text("TOKEN=sk-policy-bypass-fixture\n", encoding="utf-8")
    calls: list[tuple[object, object]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("directory-recursive grep must not reach subprocess")

    monkeypatch.setattr(sandbox_module.subprocess, "run", fake_run)

    # When: an approved grep uses directory recursion options.
    response = _broker(root).dispatch(
        capability_id="terminal.run",
        payload=payload,
        context=_authority(root),
        profile=PROFILE,
        approval_receipts=[_approval()],
        criterion_id=WAVE3_POLICY_REQ,
    )

    # Then: sandbox policy blocks the recursive form before subprocess.
    assert response["decision"] == "blocked"
    assert response["reason"] == "recursive_grep_blocked"
    assert response["result"]["handler_executed"] is False
    assert calls == []
