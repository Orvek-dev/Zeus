from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=sk",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


class ApprovalCockpitResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report", "blocked"]
    approval_gate_count: int
    required_gate_count: int
    selected_gate: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    recommended_next_commands: tuple[str, ...]
    approval_granted: bool = False
    authority_widened: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class ApprovalCockpitRuntime:
    def build(self, *, approval_id: Optional[str] = None) -> ApprovalCockpitResult:
        gates = _approval_gates()
        selected = _find_selected_gate(gates, approval_id)
        blocked_reasons = _blocked_reasons(approval_id=approval_id, selected_gate=selected)
        result = ApprovalCockpitResult(
            decision="blocked" if blocked_reasons else "report",
            approval_gate_count=len(gates),
            required_gate_count=sum(1 for gate in gates if bool(gate["human_prompt_required"])),
            selected_gate=selected,
            blocked_reasons=blocked_reasons,
            recommended_next_commands=_recommended_next_commands(approval_id=approval_id),
            approval_granted=False,
            authority_widened=False,
            credential_material_accessed=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _approval_gates() -> tuple[dict[str, JsonValue], ...]:
    return (
        _gate(
            approval_id="provider-live",
            risk_kind="external_provider_network",
            risk_summary="External model calls can expose prompts, incur model cost, and depend on provider availability.",
            required_scope="provider.external.generate",
        ),
        _gate(
            approval_id="mcp-live",
            risk_kind="mcp_server_tool_surface",
            risk_summary="MCP server calls can expose tool schemas, tool descriptions, resources, and prompts to connected runtimes.",
            required_scope="mcp.echo",
        ),
        _gate(
            approval_id="destructive-action",
            risk_kind="destructive_local_action",
            risk_summary="Local destructive actions can delete, overwrite, or irreversibly mutate workspace state.",
            required_scope="terminal.destructive",
        ),
        _gate(
            approval_id="credential-access",
            risk_kind="credential_material_access",
            risk_summary="Credential access can expose private tokens or bind credentials to the wrong endpoint.",
            required_scope="secret.read",
        ),
        _gate(
            approval_id="external-delivery",
            risk_kind="external_delivery",
            risk_summary="External delivery can send data to Slack, email, webhooks, or other third-party targets.",
            required_scope="gateway.webhook.dispatch",
            target_allowlist_required=True,
        ),
        _gate(
            approval_id="plugin-promotion",
            risk_kind="plugin_supply_chain_promotion",
            risk_summary="Plugin promotion can add untrusted code, dependencies, or tool descriptions to the runtime.",
            required_scope="plugin.promote",
        ),
    )


def _gate(
    *,
    approval_id: str,
    risk_kind: str,
    risk_summary: str,
    required_scope: str,
    target_allowlist_required: bool = False,
) -> dict[str, JsonValue]:
    return {
        "approval_id": approval_id,
        "risk_kind": risk_kind,
        "risk_summary": risk_summary,
        "required_scope": required_scope,
        "human_prompt_required": True,
        "approval_granted": False,
        "target_allowlist_required": target_allowlist_required,
        "lease_required": True,
        "evidence_required": True,
        "authority_widened": False,
        "network_opened": False,
        "handler_executed": False,
        "external_delivery_opened": False,
        "live_production_claimed": False,
    }


def _find_selected_gate(
    gates: tuple[dict[str, JsonValue], ...],
    approval_id: Optional[str],
) -> Optional[dict[str, JsonValue]]:
    if approval_id is None:
        return None
    for gate in gates:
        if gate["approval_id"] == approval_id:
            return gate
    return None


def _blocked_reasons(
    *,
    approval_id: Optional[str],
    selected_gate: Optional[dict[str, JsonValue]],
) -> tuple[str, ...]:
    if approval_id is not None and selected_gate is None:
        return ("unknown_approval_gate",)
    return ()


def _recommended_next_commands(*, approval_id: Optional[str]) -> tuple[str, ...]:
    if approval_id is None:
        return (
            "zeus approvals --approval-id provider-live --json",
            "zeus security --json",
            "zeus live --json",
        )
    return (
        "zeus security --json",
        "zeus live --json",
        "zeus platform --json",
    )


def _no_secret_echo(result: ApprovalCockpitResult) -> bool:
    serialized = json.dumps(result.to_payload(), sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
