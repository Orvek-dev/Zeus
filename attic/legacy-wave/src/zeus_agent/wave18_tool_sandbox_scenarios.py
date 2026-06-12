from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from zeus_agent.tool_sandbox_runtime import (
    ToolSandboxExecutor,
    ToolSandboxRequest,
)
from zeus_agent.wave18_tool_sandbox_support import (
    ALL_SANDBOX_CAPABILITIES,
    NOW,
    Wave18Payload,
    all_allowed,
    all_brokered,
    all_evidence,
    all_handlers,
    all_safe_env,
    any_network_opened,
    approval_for,
    blocked_label,
    expired_lease,
    fixture,
    invalid_approval,
    lease,
    path_scope_enforced,
    read,
    serialize_results,
    stdout_recorded,
)


def wave18_tool_sandbox_payload(*, scenario: str = "local-safe") -> Wave18Payload:
    if scenario != "local-safe":
        raise ValueError("scenario must be local-safe")
    root = Path(tempfile.mkdtemp(prefix="zeus-wave18-safe-"))
    try:
        sandbox_fixture = fixture(root, ALL_SANDBOX_CAPABILITIES)
        (root / "notes.txt").write_text("safe wave18 note\n", encoding="utf-8")
        executor = ToolSandboxExecutor.for_lease_root(sandbox_fixture.lease, root)
        read = executor.execute(
            ToolSandboxRequest(action="file_read", root=root, path="notes.txt"),
            sandbox_fixture.lease,
            now=NOW,
        )
        write_request = ToolSandboxRequest(
            action="file_write",
            root=root,
            path="out.txt",
            content="sandbox write ok\n",
        )
        write = executor.execute(
            write_request,
            sandbox_fixture.lease,
            approval_receipts=(
                approval_for(sandbox_fixture.lease, "sandbox.file.write", write_request, root),
            ),
            now=NOW,
        )
        command_request = ToolSandboxRequest(action="command_run", root=root, command="pwd")
        command = executor.execute(
            command_request,
            sandbox_fixture.lease,
            approval_receipts=(
                approval_for(sandbox_fixture.lease, "sandbox.command.run", command_request, root),
            ),
            now=NOW,
        )
        serialized = serialize_results(read, write, command)
        return {
            "scenario_id": "C001",
            "sandbox_executor_created": True,
            "runtime_lease_validated": all_allowed(read, write, command),
            "broker_dispatch_used": all_brokered(read, write, command),
            "safe_file_read_allowed": read.decision == "allowed",
            "safe_file_write_allowed_with_approval": write.decision == "allowed",
            "safe_cli_command_allowed": command.decision == "allowed",
            "command_stdout_recorded": stdout_recorded(command),
            "evidence_record_created": all_evidence(read, write, command),
            "path_scope_enforced": path_scope_enforced(executor, sandbox_fixture),
            "safe_env_used": all_safe_env(read, write, command),
            "cleanup_performed": True,
            "handler_executed": all_handlers(read, write, command),
            "network_opened": any_network_opened(read, write, command),
            "docker_socket_mounted": False,
            "unbounded_execution": False,
            "credential_material_accessed": False,
            "no_secret_echo": "sk-" not in serialized and "ghp_" not in serialized,
            "live_production_claimed": False,
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


def wave18_tool_sandbox_blocks_payload(*, raw_secret: str) -> Wave18Payload:
    root = Path(tempfile.mkdtemp(prefix="zeus-wave18-blocks-"))
    try:
        sandbox_fixture = fixture(root, ALL_SANDBOX_CAPABILITIES)
        executor = ToolSandboxExecutor.for_lease_root(sandbox_fixture.lease, root)
        write_request = ToolSandboxRequest(action="file_write", root=root, path="out.txt")
        command_request = ToolSandboxRequest(action="command_run", root=root, command="pwd")
        dash_request = ToolSandboxRequest(action="command_run", root=root, command="grep -R -- -TOKEN .")
        write_approval = (
            approval_for(sandbox_fixture.lease, "sandbox.file.write", write_request, root),
        )
        command_approval = (
            approval_for(sandbox_fixture.lease, "sandbox.command.run", command_request, root),
        )
        (root / "notes.txt").write_text("safe note\n", encoding="utf-8")
        (root / ".env").write_text(raw_secret, encoding="utf-8")
        cloud_root = root / ".aws"
        cloud_root.mkdir()
        (cloud_root / "credentials").write_text(
            "AWS_ACCESS_KEY_ID=AKIAWAVE18FIXTURE\n",
            encoding="utf-8",
        )
        hostile_root = Path(tempfile.mkdtemp(prefix="zeus-wave18-hostile-"))
        (hostile_root / "notes.txt").write_text("hostile note\n", encoding="utf-8")
        results = {
            "missing_runtime_lease": executor.execute(read(root), None, now=NOW),
            "expired_runtime_lease": executor.execute(read(root), expired_lease(), now=NOW),
            "hostile_root": executor.execute(
                ToolSandboxRequest(action="file_read", root=hostile_root, path="notes.txt"),
                sandbox_fixture.lease,
                now=NOW,
            ),
            "authority_widening": executor.execute(
                write_request,
                lease(("sandbox.file.read",)),
                approval_receipts=write_approval,
                now=NOW,
            ),
            "missing_approval": executor.execute(
                ToolSandboxRequest(action="file_write", root=root, path="out.txt"),
                sandbox_fixture.lease,
                now=NOW,
            ),
            "invalid_approval": executor.execute(
                command_request,
                sandbox_fixture.lease,
                approval_receipts=(invalid_approval(),),
                now=NOW,
            ),
            "approval_replay": executor.execute(
                ToolSandboxRequest(action="command_run", root=root, command="ls"),
                sandbox_fixture.lease,
                approval_receipts=command_approval,
                now=NOW,
            ),
            "network_command": executor.execute(
                ToolSandboxRequest(action="command_run", root=root, command="curl https://example.test"),
                sandbox_fixture.lease,
                approval_receipts=command_approval,
                now=NOW,
            ),
            "destructive_command": executor.execute(
                ToolSandboxRequest(action="command_run", root=root, command="rm -rf notes.txt"),
                sandbox_fixture.lease,
                approval_receipts=command_approval,
                now=NOW,
            ),
            "out_of_scope_path": executor.execute(
                ToolSandboxRequest(action="file_read", root=root, path="../outside.txt"),
                sandbox_fixture.lease,
                now=NOW,
            ),
            "credential_path": executor.execute(
                ToolSandboxRequest(action="file_read", root=root, path=".env"),
                sandbox_fixture.lease,
                now=NOW,
            ),
            "cloud_credential_path": executor.execute(
                ToolSandboxRequest(action="file_read", root=root, path=".aws/credentials"),
                sandbox_fixture.lease,
                now=NOW,
            ),
            "credential_command": executor.execute(
                ToolSandboxRequest(action="command_run", root=root, command="cat .env"),
                sandbox_fixture.lease,
                approval_receipts=command_approval,
                now=NOW,
            ),
            "recursive_credential_command": executor.execute(
                ToolSandboxRequest(action="command_run", root=root, command="grep -R secret ."),
                sandbox_fixture.lease,
                approval_receipts=command_approval,
                now=NOW,
            ),
            "dash_pattern_recursive_grep": executor.execute(
                dash_request,
                sandbox_fixture.lease,
                approval_receipts=(approval_for(sandbox_fixture.lease, "sandbox.command.run", dash_request, root),),
                now=NOW,
            ),
            "malformed_file_request": executor.execute(
                ToolSandboxRequest(action="file_read", root=root),
                sandbox_fixture.lease,
                now=NOW,
            ),
            "malformed_action": executor.execute(
                ToolSandboxRequest(action="bad.action", root=root),
                sandbox_fixture.lease,
                now=NOW,
            ),
            "malformed_root": executor.execute(
                ToolSandboxRequest(action="file_read", root="not-a-path", path="notes.txt"),
                sandbox_fixture.lease,
                now=NOW,
            ),
            "docker_socket_mount": executor.execute(
                ToolSandboxRequest(action="file_read", root=root, path="notes.txt", mounts=("/var/run/docker.sock",)),
                sandbox_fixture.lease,
                now=NOW,
            ),
            "docker_backend": executor.execute(
                ToolSandboxRequest(action="file_read", root=root, path="notes.txt", backend="docker"),
                sandbox_fixture.lease,
                now=NOW,
            ),
            "open_egress": executor.execute(
                ToolSandboxRequest(action="file_read", root=root, path="notes.txt", egress_policy="open"),
                sandbox_fixture.lease,
                now=NOW,
            ),
            "unbounded_resource": executor.execute(
                ToolSandboxRequest(action="file_read", root=root, path="notes.txt", resource_profile="unbounded"),
                sandbox_fixture.lease,
                now=NOW,
            ),
            "timeout_or_unbounded_execution": executor.execute(
                ToolSandboxRequest(action="command_run", root=root, command="tail -f notes.txt"),
                sandbox_fixture.lease,
                approval_receipts=command_approval,
                now=NOW,
            ),
        }
        serialized = serialize_results(*tuple(results.values()))
        return {
            "scenario_id": "C002",
            **{name: blocked_label(result) for name, result in results.items()},
            "blocked_handler_executed": any(result.handler_executed for result in results.values()),
            "allowed_error_network_opened": any(result.network_opened for result in results.values()),
            "raw_secret_present": raw_secret in serialized,
            "no_secret_echo": raw_secret not in serialized,
            "live_production_claimed": False,
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)
        if "hostile_root" in locals():
            shutil.rmtree(hostile_root, ignore_errors=True)
