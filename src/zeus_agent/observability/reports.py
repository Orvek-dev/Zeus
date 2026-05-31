"""Local observability reports."""

from __future__ import annotations

from pathlib import Path

from zeus_agent.core.plugins import list_plugins
from zeus_agent.core.registry import list_model_routes, list_providers, list_tools
from zeus_agent.core.scheduler import list_cron_jobs
from zeus_agent.gateway.adapters import list_gateway_adapters
from zeus_agent.paths import init_home, state_db_path
from zeus_agent.runtime.backends import DEFAULT_RUNTIME_BACKENDS
from zeus_agent.storage.run_store import RunStore
from zeus_agent.storage.state import StateStore


def build_system_report(*, home: Path | None = None) -> dict[str, object]:
    paths = init_home(home)
    store = RunStore(paths["home"])
    state = StateStore(paths["home"])
    return {
        "schema_version": "zeus.system_report.v1",
        "home": str(paths["home"]),
        "state_db": str(state_db_path(paths["home"])),
        "runs": store.list_runs(limit=10),
        "providers": [provider.model_dump(mode="json") for provider in list_providers(home=paths["home"])],
        "model_routes": [route.model_dump(mode="json") for route in list_model_routes(home=paths["home"])],
        "tools": [tool.model_dump(mode="json") for tool in list_tools(home=paths["home"])],
        "runtime_backends": [backend.__dict__ for backend in DEFAULT_RUNTIME_BACKENDS.list()],
        "plugins": [plugin.model_dump(mode="json") for plugin in list_plugins(home=paths["home"])],
        "cron_jobs": [job.model_dump(mode="json") for job in list_cron_jobs(home=paths["home"])],
        "gateway_adapters": [adapter.model_dump(mode="json") for adapter in list_gateway_adapters(home=paths["home"])],
        "recent_artifacts": state.recent_artifacts(limit=10),
    }

