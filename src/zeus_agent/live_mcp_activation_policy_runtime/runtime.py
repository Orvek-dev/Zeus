from __future__ import annotations

import hashlib
import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.mcp_runtime.catalog import McpCatalogEntry, default_mcp_catalog_entries

LiveMcpActivationPolicyDecision = Literal["policy_ready", "activation_planned", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class LiveMcpActivationPolicyResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveMcpActivationPolicyDecision
    policy_id: Optional[str]
    server_id: str
    display_name: Optional[str]
    transport: Optional[str]
    source_ref: Optional[str]
    credential_scope: Optional[str]
    approval_ref: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    server_known: bool = False
    beta_enabled: bool = False
    source_pinned: bool = False
    approval_bound: bool = False
    startup_requested: bool = False
    resources_requested: bool = False
    prompts_requested: bool = False
    server_start_allowed: bool = False
    resources_enabled: bool = False
    prompts_enabled: bool = False
    server_started: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
    recommended_next_commands: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class LiveMcpActivationPolicyRuntime:
    def plan(
        self,
        *,
        server_id: str,
        startup_requested: bool = False,
        resources_requested: bool = False,
        prompts_requested: bool = False,
        approval_ref: Optional[str] = None,
    ) -> LiveMcpActivationPolicyResult:
        safe_server_id = server_id.strip()
        safe_approval = None if approval_ref is None else approval_ref.strip() or None
        entry = _find_server(safe_server_id)
        reasons = _policy_reasons(
            server_id=safe_server_id,
            entry=entry,
            startup_requested=startup_requested,
            resources_requested=resources_requested,
            prompts_requested=prompts_requested,
            approval_ref=safe_approval,
        )
        decision = _decision(startup_requested=startup_requested, blocked_reasons=reasons)
        return LiveMcpActivationPolicyResult(
            decision=decision,
            policy_id=_policy_id(safe_server_id, safe_approval, startup_requested) if not reasons else None,
            server_id=safe_server_id,
            display_name=None if entry is None else entry.display_name,
            transport=None if entry is None else entry.transport,
            source_ref=None if entry is None else entry.source_ref,
            credential_scope=None if entry is None else entry.credential_scope,
            approval_ref=safe_approval,
            blocked_reasons=reasons,
            server_known=entry is not None,
            beta_enabled=False if entry is None else entry.beta_enabled,
            source_pinned=False if entry is None else entry.source_pinned,
            approval_bound=safe_approval is not None,
            startup_requested=startup_requested,
            resources_requested=resources_requested,
            prompts_requested=prompts_requested,
            server_start_allowed=decision == "activation_planned",
            resources_enabled=False,
            prompts_enabled=False,
            server_started=False,
            network_opened=False,
            handler_executed=False,
            credential_material_accessed=False,
            live_production_claimed=False,
            recommended_next_commands=_recommended_next_commands(decision),
        )


def _find_server(server_id: str) -> Optional[McpCatalogEntry]:
    for entry in default_mcp_catalog_entries():
        if entry.server_id == server_id:
            return entry
    return None


def _policy_reasons(
    *,
    server_id: str,
    entry: Optional[McpCatalogEntry],
    startup_requested: bool,
    resources_requested: bool,
    prompts_requested: bool,
    approval_ref: Optional[str],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if server_id == "":
        reasons.append("server_id_required")
    if entry is None:
        reasons.append("unknown_mcp_server")
    elif not entry.beta_enabled:
        reasons.append("mcp_server_not_beta_enabled")
    elif not entry.source_pinned:
        reasons.append("mcp_server_source_unpinned")
    if startup_requested and approval_ref is None:
        reasons.append("mcp_server_start_requires_approval")
    if resources_requested:
        reasons.append("mcp_resources_require_separate_policy")
    if prompts_requested:
        reasons.append("mcp_prompts_require_separate_policy")
    return tuple(dict.fromkeys(reasons))


def _decision(*, startup_requested: bool, blocked_reasons: tuple[str, ...]) -> LiveMcpActivationPolicyDecision:
    if blocked_reasons:
        return "blocked"
    if startup_requested:
        return "activation_planned"
    return "policy_ready"


def _policy_id(server_id: str, approval_ref: Optional[str], startup_requested: bool) -> str:
    payload = {"approval_ref": approval_ref, "server_id": server_id, "startup_requested": startup_requested}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-mcp-activation-policy-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _recommended_next_commands(decision: LiveMcpActivationPolicyDecision) -> tuple[str, ...]:
    if decision == "activation_planned":
        return ("zeus mcp --server-id <server> --json", "zeus live-readiness --json")
    if decision == "policy_ready":
        return ("zeus mcp --server-id <server> --json", "zeus live-mcp-request-envelope --json")
    return ("zeus mcp-catalog --json", "zeus approval-receipt --json")
