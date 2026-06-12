from __future__ import annotations

import json

from zeus_agent.kernel.authority import (
    AuthorityContext,
    CapabilityGrant,
    CredentialGrant,
    NetworkGrant,
)
from zeus_agent.model_runtime.execution import (
    ProviderExecutionRequest,
    ProviderExecutionRuntime,
)


def _authority(
    capability_ids: list[str],
    *,
    network_hosts: list[tuple[str, str]] | None = None,
    credential_scopes: list[tuple[str, str]] | None = None,
) -> AuthorityContext:
    return AuthorityContext(
        principal_id="wave5-principal",
        run_id="wave5-run",
        goal_contract_id="wave5-goal",
        capability_grants=[
            CapabilityGrant(capability_id=capability_id)
            for capability_id in capability_ids
        ],
        network_grants=[
            NetworkGrant(capability_id=capability_id, network_host=network_host)
            for capability_id, network_host in network_hosts or []
        ],
        credential_grants=[
            CredentialGrant(
                capability_id=capability_id,
                credential_scope=credential_scope,
            )
            for capability_id, credential_scope in credential_scopes or []
        ],
    )


def test_provider_runtime_selects_local_private_route_without_network_or_credentials() -> None:
    # Given: local-private provider authority and no network or credential grant.
    runtime = ProviderExecutionRuntime()
    request = ProviderExecutionRequest(
        provider="local",
        prompt="summarize local context",
        local_private=True,
        required_json_mode=True,
        required_streaming=True,
    )

    # When: the provider runtime builds a runnable dry-run envelope.
    result = runtime.prepare(request, _authority(["provider.local.generate"]))

    # Then: the selected envelope is local-only and has no external side effects.
    assert result.decision == "selected"
    assert result.reason is None
    assert result.envelope is not None
    assert result.envelope.provider == "local"
    assert result.envelope.provider_id == "local-private"
    assert result.envelope.model_id == "local-private-stub"
    assert result.envelope.local_private is True
    assert result.envelope.transport == "dry_run"
    assert result.envelope.network_allowed is False
    assert result.envelope.credential_scope_label is None
    assert result.envelope.raw_env_reads is False
    assert result.envelope.credential_material_accessed is False
    assert result.envelope.side_effects is False


def test_external_provider_envelope_uses_scope_label_when_authority_allows_transport() -> None:
    # Given: explicit network and credential authority for an external provider route.
    runtime = ProviderExecutionRuntime()
    capability_id = "provider.external.generate"
    request = ProviderExecutionRequest(
        provider="external",
        prompt="draft a plan",
        required_tool_calling=True,
        required_json_mode=True,
        network_host="api.openai.local",
        credential_scope="external.openai.readonly",
    )

    # When: the runtime prepares the external request envelope.
    result = runtime.prepare(
        request,
        _authority(
            [capability_id],
            network_hosts=[(capability_id, "api.openai.local")],
            credential_scopes=[(capability_id, "external.openai.readonly")],
        ),
    )

    # Then: the envelope contains only scope labels and remains dry-run.
    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    assert result.decision == "selected"
    assert result.envelope is not None
    assert result.envelope.provider == "external"
    assert result.envelope.provider_id == "external"
    assert result.envelope.network_allowed is True
    assert result.envelope.network_host == "api.openai.local"
    assert result.envelope.credential_scope_label == "external.openai.readonly"
    assert result.envelope.transport == "dry_run"
    assert result.envelope.raw_env_reads is False
    assert result.envelope.credential_material_accessed is False
    assert result.envelope.side_effects is False
    assert "OPENAI_API_KEY" not in serialized
    assert "sk-" not in serialized


def test_external_provider_blocks_without_network_authority() -> None:
    # Given: credential authority exists, but network authority is intentionally absent.
    runtime = ProviderExecutionRuntime()
    capability_id = "provider.external.generate"
    request = ProviderExecutionRequest(
        provider="external",
        prompt="draft a plan",
        network_host="api.openai.local",
        credential_scope="external.openai.readonly",
    )

    # When: the runtime checks transport authority before building an external envelope.
    result = runtime.prepare(
        request,
        _authority(
            [capability_id],
            credential_scopes=[(capability_id, "external.openai.readonly")],
        ),
    )

    # Then: the route is blocked and no request envelope is emitted.
    assert result.decision == "blocked"
    assert result.reason == "network_scope_missing"
    assert result.envelope is None
    assert result.route.network_allowed is False


def test_provider_runtime_rejects_secret_like_credential_scope_without_echoing_it() -> None:
    # Given: a caller mistakenly supplies raw secret material as a credential scope.
    raw_secret = "ghp_TEST_FIXTURE"
    runtime = ProviderExecutionRuntime()
    request = ProviderExecutionRequest(
        provider="external",
        prompt="draft a plan",
        network_host="api.openai.local",
        credential_scope=raw_secret,
    )

    # When: the provider runtime parses the credential boundary.
    result = runtime.prepare(request, _authority(["provider.external.generate"]))

    # Then: execution is blocked and the raw secret never appears in structured output.
    serialized = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    assert result.decision == "blocked"
    assert result.reason == "secret_like_credential_scope"
    assert result.envelope is None
    assert raw_secret not in serialized
