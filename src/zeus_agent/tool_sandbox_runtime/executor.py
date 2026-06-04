from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Optional

from zeus_agent.capability_runtime import SandboxPolicy
from zeus_agent.kernel.authority import ApprovalReceipt
from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.runtime_lease.builder import RuntimeIntakeRequest, RuntimeLeaseBuilder

from .executor_dispatch import (
    blocked_result,
    capability_graph,
    from_broker,
    handlers,
    payload_for_broker,
)
from .executor_policy import (
    CAPABILITY_BY_ACTION,
    approval_block,
    approved_root,
    authority_with_path_grant,
    preflight,
    sandbox_request_fingerprint,
    scoped_path,
)
from .models import ToolSandboxRequest, ToolSandboxResult


class ToolSandboxExecutor:
    def __init__(
        self,
        *,
        policy: Optional[SandboxPolicy] = None,
        lease_builder: Optional[RuntimeLeaseBuilder] = None,
        sandbox_roots: Optional[Mapping[str, Path]] = None,
    ) -> None:
        self._policy = policy or SandboxPolicy()
        self._lease_builder = lease_builder or RuntimeLeaseBuilder()
        self._sandbox_roots = {
            lease_id: root.resolve()
            for lease_id, root in (sandbox_roots or {}).items()
        }

    @classmethod
    def for_lease_root(
        cls,
        lease: RuntimeLease,
        root: Path,
        *,
        policy: Optional[SandboxPolicy] = None,
        lease_builder: Optional[RuntimeLeaseBuilder] = None,
    ) -> "ToolSandboxExecutor":
        return cls(
            policy=policy,
            lease_builder=lease_builder,
            sandbox_roots={lease.lease_id: root},
        )

    def execute(
        self,
        request: ToolSandboxRequest,
        lease: object,
        *,
        approval_receipts: Sequence[ApprovalReceipt] = (),
        now: Optional[datetime] = None,
    ) -> ToolSandboxResult:
        capability_id = CAPABILITY_BY_ACTION.get(request.action)
        if capability_id is None:
            return blocked_result(request, "malformed_action")
        auth = self._lease_builder.authorize(
            lease,
            RuntimeIntakeRequest(
                runtime_kind="sandbox",
                capability_id=capability_id,
                budget_required=request.budget_required,
                evidence_target=request.evidence_target,
            ),
            now=now,
        )
        if auth.decision != "allowed" or auth.authority is None:
            return blocked_result(request, auth.reason)
        root_decision = approved_root(request, lease, self._sandbox_roots)
        if root_decision.reason is not None or root_decision.root is None:
            return blocked_result(request, root_decision.reason or "sandbox_root_unbound")
        preflight_reason = preflight(self._policy, request, root_decision.root)
        if preflight_reason is not None:
            return blocked_result(request, preflight_reason)
        request_fingerprint = sandbox_request_fingerprint(request, root_decision.root)
        approval_reason = approval_block(
            request,
            auth.authority,
            approval_receipts,
            request_fingerprint=request_fingerprint,
            now=now,
        )
        if approval_reason is not None:
            return blocked_result(request, approval_reason)
        scoped = scoped_path(request, root_decision.root)
        broker = CapabilityBroker(capability_graph(), handlers(self._policy))
        response = broker.dispatch(
            capability_id=capability_id,
            payload=payload_for_broker(request, root_decision.root, scoped),
            context=authority_with_path_grant(auth.authority, capability_id, scoped),
            approval_receipts=approval_receipts,
            criterion_id="REQ-ZEUS-SANDBOX-001:S1",
        )
        return from_broker(request, response, len(broker.evidence_records))


__all__ = ["ToolSandboxExecutor", "sandbox_request_fingerprint"]
