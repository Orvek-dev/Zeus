from __future__ import annotations

from typing import Final

from pydantic import JsonValue

from zeus_agent.live_research_adapter_catalog_runtime.models import LiveResearchAdapterSpec

_ADAPTERS: Final[tuple[LiveResearchAdapterSpec, ...]] = (
    LiveResearchAdapterSpec(
        adapter_id="github",
        display_name="GitHub",
        source_id="github",
        client_module="zeus_agent.live_research_github_owned_client.GitHubResearchOwnedClient",
        default_endpoint="https://api.github.com/search/repositories",
        credential_scope="external.github.readonly",
    ),
    LiveResearchAdapterSpec(
        adapter_id="web",
        display_name="Web Search",
        source_id="web",
        client_module="zeus_agent.live_research_web_owned_client.WebResearchOwnedClient",
        endpoint_config_required=True,
    ),
    LiveResearchAdapterSpec(
        adapter_id="community",
        display_name="Developer Community",
        source_id="community",
        client_module="zeus_agent.live_research_community_owned_client.CommunityResearchOwnedClient",
        endpoint_config_required=True,
    ),
)


def live_research_adapter_catalog() -> tuple[LiveResearchAdapterSpec, ...]:
    return _ADAPTERS


def live_research_adapter_catalog_payload() -> dict[str, JsonValue]:
    adapters = live_research_adapter_catalog()
    production_ready = [adapter for adapter in adapters if adapter.production_fetcher_configured]
    return {
        "adapter_count": len(adapters),
        "owned_client_adapter_count": sum(1 for adapter in adapters if adapter.owned_client_supported),
        "production_ready_count": len(production_ready),
        "source": "local",
        "network_opened": False,
        "live_production_claimed": False,
        "adapters": [adapter.model_dump(mode="json") for adapter in adapters],
    }
