from __future__ import annotations

import json
from pathlib import Path

import pytest

from zeus_agent.capability_runtime import sandbox as sandbox_module
from zeus_agent.tool_sandbox_runtime import ToolSandboxExecutor, ToolSandboxRequest
from zeus_agent.wave18_tool_sandbox_support import (
    ALL_SANDBOX_CAPABILITIES,
    NOW,
    approval_for,
    fixture,
)
from zeus_agent.wave18_tool_sandbox_scenarios import (
    wave18_tool_sandbox_blocks_payload,
    wave18_tool_sandbox_payload,
)


def test_wave18_tool_sandbox_executes_safe_local_file_and_cli_actions() -> None:
    # Given: a controlled local sandbox root with safe file and CLI actions.
    payload = wave18_tool_sandbox_payload()

    # Then: allowed actions execute only through lease, approval, broker, and policy.
    assert payload["scenario_id"] == "C001"
    assert payload["sandbox_executor_created"] is True
    assert payload["runtime_lease_validated"] is True
    assert payload["broker_dispatch_used"] is True
    assert payload["safe_file_read_allowed"] is True
    assert payload["safe_file_write_allowed_with_approval"] is True
    assert payload["safe_cli_command_allowed"] is True
    assert payload["command_stdout_recorded"] is True
    assert payload["evidence_record_created"] is True
    assert payload["path_scope_enforced"] is True
    assert payload["safe_env_used"] is True
    assert payload["cleanup_performed"] is True
    assert payload["handler_executed"] is True
    assert payload["network_opened"] is False
    assert payload["docker_socket_mounted"] is False
    assert payload["unbounded_execution"] is False
    assert payload["credential_material_accessed"] is False
    assert payload["no_secret_echo"] is True
    assert payload["live_production_claimed"] is False


def test_wave18_tool_sandbox_blocks_unsafe_local_execution_paths() -> None:
    # Given: unsafe lease, command, file, backend, and resource requests.
    raw_secret = "sk-wave18-fixture"

    # When: the block scenario evaluates them.
    payload = wave18_tool_sandbox_blocks_payload(raw_secret=raw_secret)
    serialized = json.dumps(payload, sort_keys=True)

    # Then: all unsafe paths fail closed before side effects or secret echo.
    assert payload["scenario_id"] == "C002"
    assert payload["missing_runtime_lease"] == "blocked"
    assert payload["expired_runtime_lease"] == "blocked"
    assert payload["hostile_root"] == "blocked"
    assert payload["authority_widening"] == "blocked"
    assert payload["missing_approval"] == "blocked"
    assert payload["invalid_approval"] == "blocked"
    assert payload["approval_replay"] == "blocked"
    assert payload["network_command"] == "blocked"
    assert payload["destructive_command"] == "blocked"
    assert payload["out_of_scope_path"] == "blocked"
    assert payload["credential_path"] == "blocked"
    assert payload["cloud_credential_path"] == "blocked"
    assert payload["credential_command"] == "blocked"
    assert payload["recursive_credential_command"] == "blocked"
    assert payload["dash_pattern_recursive_grep"] == "blocked"
    assert payload["malformed_file_request"] == "blocked"
    assert payload["malformed_action"] == "blocked"
    assert payload["malformed_root"] == "blocked"
    assert payload["docker_socket_mount"] == "blocked"
    assert payload["docker_backend"] == "blocked"
    assert payload["open_egress"] == "blocked"
    assert payload["unbounded_resource"] == "blocked"
    assert payload["timeout_or_unbounded_execution"] == "blocked"
    assert payload["blocked_handler_executed"] is False
    assert payload["allowed_error_network_opened"] is False
    assert payload["raw_secret_present"] is False
    assert raw_secret not in serialized
    assert payload["no_secret_echo"] is True
    assert payload["live_production_claimed"] is False


def test_tool_sandbox_executor_blocks_unknown_action_without_raising(tmp_path: Path) -> None:
    # Given: a runtime lease and a request carrying an unknown action value.
    root = tmp_path / "sandbox"
    root.mkdir()
    sandbox_fixture = fixture(root, ALL_SANDBOX_CAPABILITIES)
    executor = ToolSandboxExecutor.for_lease_root(sandbox_fixture.lease, root)
    request = ToolSandboxRequest(action="bad.action", root=root)

    # When: the executor receives the malformed action request.
    result = executor.execute(request, sandbox_fixture.lease, now=NOW)

    # Then: it fails closed instead of raising.
    assert result.decision == "blocked"
    assert result.reason == "malformed_action"
    assert result.handler_executed is False


def test_tool_sandbox_executor_blocks_non_path_root_without_raising(tmp_path: Path) -> None:
    # Given: a runtime lease and a request carrying a non-Path root value.
    root = tmp_path / "sandbox"
    root.mkdir()
    sandbox_fixture = fixture(root, ALL_SANDBOX_CAPABILITIES)
    executor = ToolSandboxExecutor.for_lease_root(sandbox_fixture.lease, root)
    request = ToolSandboxRequest(action="file_read", root="not-a-path", path="notes.txt")

    # When: the executor receives the malformed root request.
    result = executor.execute(request, sandbox_fixture.lease, now=NOW)

    # Then: it fails closed instead of raising.
    assert result.decision == "blocked"
    assert result.reason == "malformed_sandbox_root"
    assert result.handler_executed is False


def test_tool_sandbox_executor_blocks_dash_pattern_recursive_grep_before_handler(
    tmp_path: Path,
) -> None:
    # Given: a sandbox with credential material matched by a dash-prefixed grep pattern.
    root = tmp_path / "sandbox"
    root.mkdir()
    (root / ".env").write_text("-TOKEN=sk-wave18-dash-fixture\n", encoding="utf-8")
    sandbox_fixture = fixture(root, ALL_SANDBOX_CAPABILITIES)
    executor = ToolSandboxExecutor.for_lease_root(sandbox_fixture.lease, root)
    request = ToolSandboxRequest(action="command_run", root=root, command="grep -R -- -TOKEN .")

    # When: the executor receives the approved recursive grep command.
    result = executor.execute(
        request,
        sandbox_fixture.lease,
        approval_receipts=(approval_for(sandbox_fixture.lease, "sandbox.command.run", request, root),),
        now=NOW,
    )

    # Then: it blocks before the sandbox command handler reads credential material.
    assert result.decision == "blocked"
    assert result.reason == "recursive_grep_blocked"
    assert result.handler_executed is False


@pytest.mark.parametrize(
    ("command", "expected_reason"),
    [
        ("grep -- -TOKEN .env", "credential_path"),
        ("grep -- -TOKEN ../outside.txt", "path_outside_sandbox"),
        ("grep --file=.env notes.txt", "credential_path"),
        ("grep --file=/etc/passwd /etc/passwd", "path_outside_sandbox"),
        ("grep -f .env notes.txt", "credential_path"),
    ],
)
def test_tool_sandbox_executor_blocks_grep_file_operand_bypasses_before_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    expected_reason: str,
) -> None:
    # Given: a sandbox with credential and safe files plus approved command authority.
    root = tmp_path / "sandbox"
    root.mkdir()
    (root / ".env").write_text("-TOKEN=sk-wave18-dash-fixture\n", encoding="utf-8")
    (root / "notes.txt").write_text("safe note\n", encoding="utf-8")
    calls: list[tuple[object, object]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("credential or out-of-scope grep must not reach subprocess")

    monkeypatch.setattr(sandbox_module.subprocess, "run", fake_run)
    sandbox_fixture = fixture(root, ALL_SANDBOX_CAPABILITIES)
    executor = ToolSandboxExecutor.for_lease_root(sandbox_fixture.lease, root)
    request = ToolSandboxRequest(action="command_run", root=root, command=command)

    # When: the executor receives approved non-recursive grep bypass forms.
    result = executor.execute(
        request,
        sandbox_fixture.lease,
        approval_receipts=(approval_for(sandbox_fixture.lease, "sandbox.command.run", request, root),),
        now=NOW,
    )

    # Then: preflight/policy blocks before the sandbox command handler reads files.
    assert result.decision == "blocked"
    assert result.reason == expected_reason
    assert result.handler_executed is False
    assert calls == []


@pytest.mark.parametrize(
    "command",
    [
        "grep -d recurse TOKEN .",
        "grep --directories=recurse TOKEN .",
        "grep --directories recurse TOKEN .",
        "grep --directories skip -R TOKEN .",
    ],
)
def test_tool_sandbox_executor_blocks_grep_directory_recurse_options_before_handler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    # Given: a sandbox with credential material and alternate recursive grep syntax.
    root = tmp_path / "sandbox"
    root.mkdir()
    (root / ".env").write_text("TOKEN=sk-wave18-recurse-fixture\n", encoding="utf-8")
    calls: list[tuple[object, object]] = []

    def fake_run(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("directory-recursive grep must not reach subprocess")

    monkeypatch.setattr(sandbox_module.subprocess, "run", fake_run)
    sandbox_fixture = fixture(root, ALL_SANDBOX_CAPABILITIES)
    executor = ToolSandboxExecutor.for_lease_root(sandbox_fixture.lease, root)
    request = ToolSandboxRequest(action="command_run", root=root, command=command)

    # When: the executor receives approved directory-recursive grep forms.
    result = executor.execute(
        request,
        sandbox_fixture.lease,
        approval_receipts=(approval_for(sandbox_fixture.lease, "sandbox.command.run", request, root),),
        now=NOW,
    )

    # Then: preflight/policy blocks before the sandbox command handler reads files.
    assert result.decision == "blocked"
    assert result.reason == "recursive_grep_blocked"
    assert result.handler_executed is False
    assert calls == []
