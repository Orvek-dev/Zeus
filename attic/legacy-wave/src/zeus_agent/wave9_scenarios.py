from __future__ import annotations

import json

from pydantic import ValidationError

from zeus_agent.runtime_lease import (
    RuntimeIntakeRequest,
    RuntimeKind,
    RuntimeLease,
    RuntimeLeaseBuilder,
    RuntimeLeaseIntakeResult,
    wave9_fixture_lease,
)


def wave9_runtime_lease_payload() -> dict[str, object]:
    lease = wave9_fixture_lease()
    builder = RuntimeLeaseBuilder()
    valid_now = lease.issued_at
    provider = builder.authorize(
        lease,
        RuntimeIntakeRequest(
            runtime_kind="provider",
            capability_id="provider.external.generate",
            credential_scope="external.openai.readonly",
            network_host="api.openai.local",
            budget_required=25,
            evidence_target=lease.evidence_target,
        ),
        now=valid_now,
    )
    mcp = builder.authorize(lease, _request("mcp", "mcp.echo", lease.evidence_target), now=valid_now)
    gateway = builder.authorize(
        lease,
        RuntimeIntakeRequest(
            runtime_kind="gateway",
            capability_id="gateway.webhook.dispatch",
            credential_scope="external.gateway.readonly",
            network_host="gateway.local",
            budget_required=10,
            evidence_target=lease.evidence_target,
        ),
        now=valid_now,
    )
    cron = builder.authorize(
        lease,
        _request("cron", "cron.schedule.tick", lease.evidence_target),
        now=valid_now,
    )
    api_tool = builder.authorize(
        lease,
        _request("api_tool", "api.tool.invoke", lease.evidence_target),
        now=valid_now,
    )
    plugin = builder.authorize(
        lease,
        _request("plugin", "plugin.local.execute", lease.evidence_target),
        now=valid_now,
    )
    results = (provider, mcp, gateway, cron, api_tool, plugin)
    authority = provider.authority
    provider_capability_grants = (
        [] if authority is None else [grant.capability_id for grant in authority.capability_grants]
    )
    provider_credential_grants = (
        []
        if authority is None
        else [
            "{0}:{1}".format(grant.capability_id, grant.credential_scope)
            for grant in authority.credential_grants
        ]
    )
    provider_network_grant_count = 0 if authority is None else len(authority.network_grants)
    payload = {
        "runtime_lease_validated": True,
        "lease_id": lease.lease_id,
        "principal_id": lease.principal_id,
        "objective_id": lease.objective_id,
        "provider_scope": _scope_label(provider),
        "mcp_scope": _scope_label(mcp),
        "gateway_scope": _scope_label(gateway),
        "cron_scope": _scope_label(cron),
        "api_tool_scope": _scope_label(api_tool),
        "plugin_scope": _scope_label(plugin),
        "credential_scope_label": provider.credential_scope_label,
        "budget_limit": lease.budget_limit,
        "evidence_target": lease.evidence_target,
        "live_transport_allowed": lease.live_transport_allowed,
        "request_scoped_authority": provider_capability_grants == ["provider.external.generate"]
        and provider_credential_grants == ["provider.external.generate:external.openai.readonly"]
        and provider_network_grant_count == 0,
        "provider_authority_capability_grants": provider_capability_grants,
        "provider_authority_credential_grants": provider_credential_grants,
        "provider_authority_network_grants": provider_network_grant_count,
        "handler_executed": any(result.handler_executed for result in results),
        "network_opened": any(result.network_opened for result in results),
    }
    return payload | {"no_secret_echo": _no_secret_echo(payload)}


def wave9_runtime_blocks_payload(*, raw_secret: str) -> dict[str, object]:
    lease = wave9_fixture_lease()
    builder = RuntimeLeaseBuilder()
    valid_now = lease.issued_at
    missing = builder.authorize(None, _request("provider", "provider.external.generate", lease.evidence_target))
    malformed_principal = _malformed_principal_label(lease)
    malformed_runtime_lease = builder.authorize(
        object(),
        _request("provider", "provider.external.generate", lease.evidence_target),
    )
    runtime_kind_mismatch = builder.authorize(
        lease,
        _request("provider", "mcp.echo", lease.evidence_target),
        now=valid_now,
    )
    authority_widening = builder.authorize(
        lease,
        _request("provider", "provider.external.admin", lease.evidence_target),
        now=valid_now,
    )
    scope_escalation = builder.authorize(
        lease,
        RuntimeIntakeRequest(
            runtime_kind="provider",
            capability_id="provider.external.generate",
            requested_capabilities=("provider.external.admin",),
            budget_required=1,
            evidence_target=lease.evidence_target,
        ),
        now=valid_now,
    )
    evidence_scope_bypass = builder.authorize(
        lease,
        RuntimeIntakeRequest(
            runtime_kind="provider",
            capability_id="provider.external.generate",
            budget_required=1,
            evidence_target="mneme.wave9.other_target",
        ),
        now=valid_now,
    )
    unsafe_credential = builder.authorize(
        lease,
        RuntimeIntakeRequest(
            runtime_kind="provider",
            capability_id="provider.external.generate",
            credential_scope=raw_secret,
            budget_required=1,
            evidence_target=lease.evidence_target,
        ),
        now=valid_now,
    )
    live_network = builder.authorize(
        lease,
        RuntimeIntakeRequest(
            runtime_kind="provider",
            capability_id="provider.external.generate",
            network_host="api.unknown.local",
            live_network=True,
            budget_required=1,
            evidence_target=lease.evidence_target,
        ),
        now=valid_now,
    )
    expired = builder.authorize(
        lease,
        _request("provider", "provider.external.generate", lease.evidence_target),
        now=lease.expires_at,
    )
    over_budget = builder.authorize(
        lease,
        RuntimeIntakeRequest(
            runtime_kind="provider",
            capability_id="provider.external.generate",
            budget_required=lease.budget_limit + 1,
            evidence_target=lease.evidence_target,
        ),
        now=valid_now,
    )
    results = (
        missing,
        malformed_runtime_lease,
        runtime_kind_mismatch,
        authority_widening,
        scope_escalation,
        evidence_scope_bypass,
        unsafe_credential,
        live_network,
        expired,
        over_budget,
    )
    payload = {
        "missing_runtime_lease": _block_label(missing, "missing_runtime_lease"),
        "malformed_principal": malformed_principal,
        "malformed_runtime_lease": _block_label(malformed_runtime_lease, "malformed_runtime_lease"),
        "runtime_kind_capability_mismatch": _block_label(
            runtime_kind_mismatch,
            "runtime_kind_capability_mismatch",
        ),
        "authority_widening": _block_label(authority_widening, "authority_widening"),
        "scope_escalation": _block_label(scope_escalation, "scope_escalation"),
        "evidence_scope_bypass": _block_label(evidence_scope_bypass, "evidence_scope_bypass"),
        "unsafe_credential": _block_label(unsafe_credential, "unsafe_credential"),
        "live_network_without_scope": _block_label(live_network, "live_network_without_scope"),
        "expired_runtime_lease": _block_label(expired, "runtime_lease_expired"),
        "over_budget": _block_label(over_budget, "over_budget"),
        "handler_executed": any(result.handler_executed for result in results),
        "network_opened": any(result.network_opened for result in results),
    }
    return payload | {"no_secret_echo": raw_secret not in json.dumps(payload, sort_keys=True)}


def _request(
    runtime_kind: RuntimeKind,
    capability_id: str,
    evidence_target: str,
) -> RuntimeIntakeRequest:
    return RuntimeIntakeRequest(
        runtime_kind=runtime_kind,
        capability_id=capability_id,
        budget_required=1,
        evidence_target=evidence_target,
    )


def _scope_label(result: RuntimeLeaseIntakeResult) -> str:
    if result.decision == "allowed":
        return "allowed"
    return result.reason


def _block_label(result: RuntimeLeaseIntakeResult, reason: str) -> str:
    if result.decision == "blocked" and result.reason == reason:
        return "blocked"
    return result.reason


def _malformed_principal_label(lease: RuntimeLease) -> str:
    raw = lease.model_dump(mode="json")
    raw["principal_id"] = "bad principal"
    try:
        RuntimeLease.model_validate(raw)
    except ValidationError:
        return "blocked"
    return "allowed"


def _no_secret_echo(payload: dict[str, object]) -> bool:
    serialized = json.dumps(payload, sort_keys=True)
    return "sk-" not in serialized and "ghp_" not in serialized
