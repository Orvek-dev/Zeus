from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Optional

from zeus_agent.capability_runtime import SandboxPolicy
from zeus_agent.kernel.authority import ApprovalReceipt, AuthorityContext, PathGrant
from zeus_agent.runtime_lease import RuntimeLease

from .models import ToolSandboxRequest

CAPABILITY_BY_ACTION: dict[str, str] = {
    "file_read": "sandbox.file.read",
    "file_write": "sandbox.file.write",
    "command_run": "sandbox.command.run",
}
APPROVAL_REQUIRED = {"file_write", "command_run"}
CREDENTIAL_NAMES = {
    ".aws",
    ".azure",
    ".docker",
    ".env",
    ".gcp",
    ".kube",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "id_ed25519",
    "id_rsa",
}


@dataclass(frozen=True)
class RootDecision:
    root: Optional[Path]
    reason: Optional[str]


def approved_root(
    request: ToolSandboxRequest,
    lease: object,
    sandbox_roots: Mapping[str, Path],
) -> RootDecision:
    if not isinstance(lease, RuntimeLease):
        return RootDecision(root=None, reason="malformed_runtime_lease")
    root = sandbox_roots.get(lease.lease_id)
    if root is None:
        return RootDecision(root=None, reason="sandbox_root_unbound")
    if not isinstance(request.root, Path):
        return RootDecision(root=None, reason="malformed_sandbox_root")
    if request.root.resolve() != root:
        return RootDecision(root=None, reason="sandbox_root_mismatch")
    return RootDecision(root=root, reason=None)


def preflight(
    policy: SandboxPolicy,
    request: ToolSandboxRequest,
    approved_root_value: Path,
) -> Optional[str]:
    if request.backend != "local":
        return "docker_backend"
    if request.egress_policy not in {"none", "denied"}:
        return "open_egress"
    if request.resource_profile != "bounded":
        return "unbounded_resource"
    for mount in request.mounts:
        if _is_docker_socket(mount):
            return "docker_socket_mount"
        mount_decision = policy.resolve_path(approved_root_value, mount)
        if mount_decision.decision == "blocked":
            return mount_decision.reason or "path_outside_sandbox"
    if request.action in {"file_read", "file_write"} and request.path is None:
        return "malformed_file_path"
    if request.path is not None:
        if _is_credential_path(request.path):
            return "credential_path"
        if policy.resolve_path(approved_root_value, request.path).decision == "blocked":
            return "out_of_scope_path"
    if request.action == "command_run":
        return _preflight_command(policy, request, approved_root_value)
    return None


def _preflight_command(
    policy: SandboxPolicy,
    request: ToolSandboxRequest,
    approved_root_value: Path,
) -> Optional[str]:
    if request.command is None:
        return "malformed_command"
    if _is_unbounded_command(request.command):
        return "timeout_or_unbounded_execution"
    decision = policy.decide_command(request.command, approved_root_value)
    if decision.decision == "blocked":
        return decision.reason or "command_blocked"
    return None


def approval_block(
    request: ToolSandboxRequest,
    authority: AuthorityContext,
    receipts: Sequence[ApprovalReceipt],
    *,
    request_fingerprint: str,
    now: Optional[datetime],
) -> Optional[str]:
    capability_id = CAPABILITY_BY_ACTION.get(request.action)
    if capability_id is None:
        return "malformed_action"
    if request.action not in APPROVAL_REQUIRED:
        return None
    if not receipts:
        return "missing_approval"
    timestamp = _to_utc(now or datetime.now(timezone.utc))
    capability_seen = False
    for receipt in receipts:
        try:
            receipt.assert_within_authority(authority)
        except ValueError:
            return "invalid_approval"
        if capability_id not in set(receipt.approved_capabilities):
            continue
        capability_seen = True
        if receipt.request_fingerprint != request_fingerprint:
            continue
        if receipt.expires_at is None or _to_utc(receipt.expires_at) <= timestamp:
            return "invalid_approval"
        return None
    return "invalid_approval" if capability_seen else "missing_approval"


def scoped_path(request: ToolSandboxRequest, approved_root_value: Path) -> str:
    if request.path is None:
        return approved_root_value.as_posix()
    return (approved_root_value / request.path).resolve().as_posix()


def authority_with_path_grant(
    authority: AuthorityContext,
    capability_id: str,
    path: str,
) -> AuthorityContext:
    return authority.model_copy(
        update={
            "path_grants": [
                *authority.path_grants,
                PathGrant(capability_id=capability_id, path_prefix=path),
            ],
        },
    )


def sandbox_request_fingerprint(request: ToolSandboxRequest, approved_root_value: Path) -> str:
    payload = {
        "action": request.action,
        "root": approved_root_value.resolve().as_posix(),
        "path": None if request.path is None else (approved_root_value / request.path).resolve().as_posix(),
        "command_sha256": _hash_optional(request.command),
        "content_sha256": _hash_optional(request.content),
        "backend": request.backend,
        "egress_policy": request.egress_policy,
        "resource_profile": request.resource_profile,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:{0}".format(sha256(serialized.encode("utf-8")).hexdigest())


def _is_credential_path(path: str) -> bool:
    parts = {part.lower() for part in Path(path).parts}
    markers = ("secret", "credential", "token", "private")
    return bool(parts.intersection(CREDENTIAL_NAMES)) or any(
        marker in part for part in parts for marker in markers
    )


def _is_docker_socket(path: str) -> bool:
    return Path(path).name == "docker.sock"


def _is_unbounded_command(command: str) -> bool:
    lowered = command.lower()
    return "tail -f" in lowered or lowered.startswith("sleep ") or lowered.startswith("yes")


def _hash_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return sha256(value.encode("utf-8")).hexdigest()


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
