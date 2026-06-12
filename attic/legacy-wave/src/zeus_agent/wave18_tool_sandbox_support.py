from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from zeus_agent.kernel.authority import ApprovalReceipt
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.tool_sandbox_runtime import (
    ToolSandboxExecutor,
    ToolSandboxRequest,
    ToolSandboxResult,
    sandbox_request_fingerprint,
)

Wave18Value = Union[bool, int, str]
Wave18Payload = dict[str, Wave18Value]

NOW = datetime(2026, 6, 3, 10, 0, tzinfo=timezone.utc)
ISSUED = datetime(2026, 6, 3, 9, 0, tzinfo=timezone.utc)
EXPIRES = datetime(2026, 6, 4, 9, 0, tzinfo=timezone.utc)
EXPIRED = datetime(2026, 6, 3, 9, 30, tzinfo=timezone.utc)
ALL_SANDBOX_CAPABILITIES = (
    "sandbox.file.read",
    "sandbox.file.write",
    "sandbox.command.run",
)


@dataclass(frozen=True)
class SandboxFixture:
    root: Path
    lease: RuntimeLease


def fixture(root: Path, capabilities: Sequence[str]) -> SandboxFixture:
    return SandboxFixture(root=root, lease=lease(tuple(capabilities)))


def lease(capabilities: tuple[str, ...]) -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave18.lease.fixture",
        objective_id="wave18.objective.sandbox",
        principal_id="wave18.principal.operator",
        run_id="wave18.run.fixture",
        allowed_capabilities=capabilities,
        budget_limit=100,
        evidence_target="mneme.wave18.tool_sandbox",
        issued_at=ISSUED,
        expires_at=EXPIRES,
    )


def expired_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave18.lease.expired",
        objective_id="wave18.objective.sandbox",
        principal_id="wave18.principal.operator",
        run_id="wave18.run.fixture",
        allowed_capabilities=ALL_SANDBOX_CAPABILITIES,
        budget_limit=100,
        evidence_target="mneme.wave18.tool_sandbox",
        issued_at=ISSUED,
        expires_at=EXPIRED,
    )


def approval_for(
    runtime_lease: RuntimeLease,
    capability_id: str,
    request: ToolSandboxRequest,
    approved_root: Path,
) -> ApprovalReceipt:
    return ApprovalReceipt(
        principal_id=runtime_lease.principal_id,
        run_id=runtime_lease.run_id,
        goal_contract_id=runtime_lease.objective_id,
        approved_capabilities=[capability_id],
        request_fingerprint=sandbox_request_fingerprint(request, approved_root),
        expires_at=EXPIRES,
        nonce="wave18.approval.{0}".format(capability_id.replace(".", "_")),
    )


def invalid_approval() -> ApprovalReceipt:
    return ApprovalReceipt(
        principal_id="wave18.principal.other",
        run_id="wave18.run.fixture",
        goal_contract_id="wave18.objective.sandbox",
        approved_capabilities=["sandbox.command.run"],
    )


def read(root: Path) -> ToolSandboxRequest:
    return ToolSandboxRequest(action="file_read", root=root, path="notes.txt")


def path_scope_enforced(
    executor: ToolSandboxExecutor,
    sandbox_fixture: SandboxFixture,
) -> bool:
    result = executor.execute(
        ToolSandboxRequest(action="file_read", root=sandbox_fixture.root, path="../outside.txt"),
        sandbox_fixture.lease,
        now=NOW,
    )
    return result.decision == "blocked" and result.reason in {
        "out_of_scope_path",
        "path_outside_sandbox",
    }


def stdout_recorded(result: ToolSandboxResult) -> bool:
    return isinstance(result.result, dict) and bool(str(result.result.get("stdout", "")).strip())


def all_allowed(*results: ToolSandboxResult) -> bool:
    return all(result.decision == "allowed" for result in results)


def all_brokered(*results: ToolSandboxResult) -> bool:
    return all(result.broker_dispatch_used for result in results)


def all_evidence(*results: ToolSandboxResult) -> bool:
    return all(result.evidence_record_created for result in results)


def all_safe_env(*results: ToolSandboxResult) -> bool:
    return all(result.safe_env_used for result in results)


def all_handlers(*results: ToolSandboxResult) -> bool:
    return all(result.handler_executed for result in results)


def any_network_opened(*results: ToolSandboxResult) -> bool:
    return any(result.network_opened for result in results)


def blocked_label(result: ToolSandboxResult) -> str:
    return "blocked" if result.decision == "blocked" else result.decision


def serialize_results(*results: ToolSandboxResult) -> str:
    return json.dumps(
        [
            {
                "decision": result.decision,
                "reason": result.reason,
                "result": result.result,
            }
            for result in results
        ],
        sort_keys=True,
    )
