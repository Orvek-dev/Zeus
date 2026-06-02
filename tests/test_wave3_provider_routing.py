from __future__ import annotations

import json

from zeus_agent.model_runtime.providers import (
    ProviderRouteRequest,
    default_provider_router,
)


def test_fake_provider_selected_when_requested_capabilities_match_fake_matrix() -> None:
    # Given: a fake-provider request requiring capabilities declared by fake_tool_matrix.
    router = default_provider_router()
    request = ProviderRouteRequest(
        provider="fake",
        required_tool_calling=True,
        required_json_mode=True,
    )

    # When: the router evaluates the pure provider declarations.
    result = router.route(request)

    # Then: the fake stub is selected without any real model boundary.
    assert result.decision == "selected"
    assert result.provider_id == "fake-local"
    assert result.model_id == "fake-tool-model"
    assert result.reason is None
    assert result.local_private is True
    assert result.tool_calling is True
    assert result.json_mode is True
    assert result.streaming is False


def test_local_provider_stub_selected_when_local_private_is_requested() -> None:
    # Given: a local-provider request that requires a private local route.
    router = default_provider_router()
    request = ProviderRouteRequest(
        provider="local",
        local_private=True,
        required_json_mode=True,
    )

    # When: the router evaluates the declared local stub.
    result = router.route(request)

    # Then: a local-private provider stub is selected.
    assert result.decision == "selected"
    assert result.provider_id == "local-private"
    assert result.model_id == "local-private-stub"
    assert result.local_private is True
    assert result.json_mode is True


def test_external_provider_blocked_when_credential_scope_is_missing() -> None:
    # Given: an external-provider request with network allowed but no credential scope.
    router = default_provider_router()
    request = ProviderRouteRequest(
        provider="external",
        network_allowed=True,
        required_json_mode=True,
    )

    # When: the router evaluates the external route.
    result = router.route(request)

    # Then: the route fails closed before provider selection.
    assert result.decision == "blocked"
    assert result.provider_id is None
    assert result.model_id is None
    assert result.reason == "missing_credential_scope"


def test_external_provider_blocked_when_network_is_not_allowed() -> None:
    # Given: an external-provider request with a credential label but no network authority.
    router = default_provider_router()
    request = ProviderRouteRequest(
        provider="external",
        credential_scope="openai-prod-readonly",
        network_allowed=False,
        required_tool_calling=True,
    )

    # When: the router evaluates the external route.
    result = router.route(request)

    # Then: no-network policy blocks the route even with credential scope present.
    assert result.decision == "blocked"
    assert result.provider_id is None
    assert result.model_id is None
    assert result.reason == "network_not_allowed"


def test_secret_like_credential_values_are_never_echoed_in_route_output() -> None:
    # Given: a caller accidentally passes a raw secret-like value as credential scope.
    router = default_provider_router()
    request = ProviderRouteRequest(
        provider="external",
        credential_scope="sk-test-secret",
        network_allowed=True,
        required_tool_calling=True,
    )

    # When: the router blocks the unsafe credential boundary.
    result = router.route(request)

    # Then: the structured result does not echo the secret-like input.
    route_blob = json.dumps(result.model_dump(mode="json"), sort_keys=True)
    assert result.decision == "blocked"
    assert result.reason == "secret_like_credential_scope"
    assert "sk-test-secret" not in route_blob
