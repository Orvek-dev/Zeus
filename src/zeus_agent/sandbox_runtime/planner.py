from __future__ import annotations

from pathlib import Path
from typing import Final

from zeus_agent.capability_runtime.sandbox import SandboxPolicy
from zeus_agent.security.credentials import redact_secret_spans

from .models import (
    CleanupObligation,
    EvidenceObligation,
    RequirementDecision,
    SandboxCommandPlan,
    SandboxDispatchRequest,
    SandboxDispatchResult,
    SandboxMountRequirement,
    SandboxPlanDecision,
    SandboxRequirement,
)


class SandboxDispatchFacade:
    def __init__(self, policy: SandboxPolicy | None = None) -> None:
        self._policy = policy or SandboxPolicy()

    def plan(self, request: SandboxDispatchRequest) -> SandboxDispatchResult:
        root = request.root.resolve() if request.root is not None else Path.cwd()
        backend = _backend_requirement(request.backend)
        mounts = tuple(_mount_requirement(self._policy, root, mount) for mount in request.mounts)
        egress = _egress_requirement(request.egress_policy)
        resource = _resource_requirement(request.resource_profile)
        cleanup = _cleanup_obligation(request.cleanup_required, request.cleanup_plan)
        commands = tuple(_command_plan(self._policy, root, command) for command in request.commands)
        blocked_reasons = _blocked_reasons(backend, mounts, egress, resource, cleanup, commands)
        decision: SandboxPlanDecision = "blocked" if blocked_reasons else "planned"
        reason = "dry_run_plan_only" if decision == "planned" else ";".join(blocked_reasons)
        return SandboxDispatchResult(
            decision=decision,
            reason=reason,
            request_id=request.request_id,
            backend_requirement=backend,
            mount_requirements=mounts,
            egress_requirement=egress,
            resource_requirement=resource,
            cleanup_obligation=cleanup,
            evidence_obligation=EvidenceObligation(
                required=True,
                target=request.evidence_target,
                reason="sandbox_dispatch_requires_evidence",
            ),
            command_plans=commands,
            blocked_reasons=blocked_reasons,
        )


SandboxDispatchPlanner = SandboxDispatchFacade
SandboxFacade = SandboxDispatchFacade


def plan_sandbox_dispatch(
    request: SandboxDispatchRequest | tuple[str, ...],
    *,
    root: Path | None = None,
    evidence_target: str | None = None,
) -> SandboxDispatchResult:
    match request:
        case SandboxDispatchRequest():
            dispatch_request = request
        case tuple():
            dispatch_request = SandboxDispatchRequest(
                root=root,
                commands=request,
                evidence_target=evidence_target,
            )
        case _:
            raise ValueError("malformed_sandbox_dispatch")
    return SandboxDispatchFacade().plan(dispatch_request)


def _backend_requirement(backend: str) -> SandboxRequirement:
    match backend:
        case "local":
            return SandboxRequirement(name="backend", value=backend, decision="planned")
        case _:
            return SandboxRequirement(
                name="backend",
                value=backend,
                decision="blocked",
                reason="backend_not_supported",
            )


def _mount_requirement(policy: SandboxPolicy, root: Path, mount: str) -> SandboxMountRequirement:
    decision = policy.resolve_path(root, mount)
    if decision.decision == "allowed" and decision.path is not None:
        return SandboxMountRequirement(
            path=mount,
            decision="planned",
            resolved_path=decision.path.as_posix(),
        )
    return SandboxMountRequirement(
        path=mount,
        decision="blocked",
        reason=decision.reason or "path_blocked",
    )


def _egress_requirement(egress_policy: str) -> SandboxRequirement:
    match egress_policy:
        case "none" | "denied":
            return SandboxRequirement(
                name="egress_policy",
                value=egress_policy,
                decision="planned",
                reason="network_egress_denied",
            )
        case _:
            return SandboxRequirement(
                name="egress_policy",
                value=egress_policy,
                decision="blocked",
                reason="network_egress_blocked",
            )


def _resource_requirement(resource_profile: str) -> SandboxRequirement:
    match resource_profile:
        case "bounded":
            return SandboxRequirement(name="resource_profile", value=resource_profile, decision="planned")
        case _:
            return SandboxRequirement(
                name="resource_profile",
                value=resource_profile,
                decision="blocked",
                reason="resource_profile_unbounded",
            )


def _cleanup_obligation(cleanup_required: bool, cleanup_plan: str | None) -> CleanupObligation:
    if not cleanup_required:
        return CleanupObligation(required=False, decision="planned", reason="cleanup_not_required")
    if cleanup_plan is None:
        return CleanupObligation(
            required=True,
            decision="blocked",
            reason="missing_cleanup_obligation",
        )
    return CleanupObligation(
        required=True,
        decision="planned",
        reason="cleanup_required_after_evidence_capture",
        plan=cleanup_plan,
    )


def _command_plan(policy: SandboxPolicy, root: Path, command: str) -> SandboxCommandPlan:
    decision = policy.decide_command(command, root)
    return SandboxCommandPlan(
        command=command,
        argv=tuple(redact_secret_spans(value) for value in decision.argv),
        decision=decision.decision,
        reason=decision.reason,
    )


def _blocked_reasons(
    backend: SandboxRequirement,
    mounts: tuple[SandboxMountRequirement, ...],
    egress: SandboxRequirement,
    resource: SandboxRequirement,
    cleanup: CleanupObligation,
    commands: tuple[SandboxCommandPlan, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    for requirement in (backend, egress, resource):
        _append_reason(reasons, requirement.reason if requirement.decision == "blocked" else None)
    for mount in mounts:
        _append_reason(reasons, mount.reason if mount.decision == "blocked" else None)
    _append_reason(reasons, cleanup.reason if cleanup.decision == "blocked" else None)
    for command in commands:
        _append_reason(reasons, command.reason if command.decision == "blocked" else None)
    return tuple(reasons)


def _append_reason(reasons: list[str], reason: str | None) -> None:
    if reason is not None and reason not in reasons:
        reasons.append(reason)


__all__: Final = (
    "CleanupObligation",
    "EvidenceObligation",
    "RequirementDecision",
    "SandboxCommandPlan",
    "SandboxDispatchFacade",
    "SandboxDispatchPlanner",
    "SandboxDispatchRequest",
    "SandboxDispatchResult",
    "SandboxFacade",
    "SandboxMountRequirement",
    "SandboxPlanDecision",
    "SandboxRequirement",
    "plan_sandbox_dispatch",
)
