from __future__ import annotations

import hashlib
import json
from typing import Mapping, Optional

from zeus_agent.live_research_adapter_catalog_runtime import live_research_adapter_catalog
from zeus_agent.live_research_adapter_catalog_runtime.models import LiveResearchAdapterSpec
from zeus_agent.live_research_workflow_runtime.models import (
    LiveResearchWorkflowResult,
    LiveResearchWorkflowSource,
)
from zeus_agent.security.credentials import redact_secret_spans


class LiveResearchWorkflowRuntime:
    def compile_workflow(
        self,
        *,
        query: str,
        objective_id: str,
        endpoint_overrides: Optional[Mapping[str, str]] = None,
    ) -> LiveResearchWorkflowResult:
        safe_query = redact_secret_spans(query.strip())
        safe_objective = redact_secret_spans(objective_id.strip())
        safe_overrides = _safe_overrides(endpoint_overrides or {})
        reasons = _blocked_reasons(query=safe_query, raw_overrides=endpoint_overrides or {})
        sources = tuple(_source(adapter, safe_overrides.get(adapter.adapter_id)) for adapter in live_research_adapter_catalog())
        ready_count = sum(1 for source in sources if source.state == "ready_for_policy")
        endpoint_required_count = sum(1 for source in sources if source.state == "endpoint_required")
        return LiveResearchWorkflowResult(
            decision="blocked" if reasons else "workflow_planned",
            plan_id=None if reasons else _plan_id(safe_objective, safe_query, safe_overrides),
            objective_id=safe_objective,
            query=safe_query,
            source_count=len(sources),
            ready_source_count=ready_count,
            endpoint_required_count=endpoint_required_count,
            sources=sources,
            blocked_reasons=tuple(dict.fromkeys(reasons)),
            no_secret_echo=_no_secret_echo(sources, reasons),
        )


def _source(adapter: LiveResearchAdapterSpec, override_endpoint: Optional[str]) -> LiveResearchWorkflowSource:
    endpoint = override_endpoint if override_endpoint is not None else adapter.default_endpoint
    endpoint_bound = endpoint is not None
    endpoint_required = adapter.endpoint_config_required and not endpoint_bound
    return LiveResearchWorkflowSource(
        adapter_id=adapter.adapter_id,
        source_id=adapter.source_id,
        display_name=adapter.display_name,
        state="endpoint_required" if endpoint_required else "ready_for_policy",
        endpoint=endpoint,
        endpoint_bound=endpoint_bound,
        credential_scope=adapter.credential_scope,
        required_controls=_required_controls(endpoint_required),
        recommended_next_commands=_recommended_commands(adapter.adapter_id, endpoint_required),
    )


def _required_controls(endpoint_required: bool) -> tuple[str, ...]:
    controls = ["approval_ref", "source_pin_ref", "source_config", "execution_plan"]
    if endpoint_required:
        controls.insert(0, "endpoint")
    return tuple(controls)


def _recommended_commands(adapter_id: str, endpoint_required: bool) -> tuple[str, ...]:
    base = "zeus live-research-source-config --adapter-id {0}".format(adapter_id)
    if endpoint_required:
        return (base + " --endpoint <endpoint> --json",)
    return (base + " --json", "zeus live-research-activation-policy --json")


def _safe_overrides(raw: Mapping[str, str]) -> dict[str, str]:
    return {redact_secret_spans(key.strip()): redact_secret_spans(value.strip()) for key, value in raw.items()}


def _blocked_reasons(*, query: str, raw_overrides: Mapping[str, str]) -> list[str]:
    reasons: list[str] = []
    if query == "":
        reasons.append("live_research_workflow_query_required")
    for value in raw_overrides.values():
        if redact_secret_spans(value.strip()) != value.strip():
            reasons.append("live_research_workflow_endpoint_contains_secret")
    return reasons


def _plan_id(objective_id: str, query: str, endpoint_overrides: Mapping[str, str]) -> str:
    payload = {"endpoint_overrides": dict(endpoint_overrides), "objective_id": objective_id, "query": query}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "live-research-workflow-{0}".format(hashlib.sha256(encoded).hexdigest()[:16])


def _no_secret_echo(sources: tuple[LiveResearchWorkflowSource, ...], reasons: list[str]) -> bool:
    payload = {"reasons": reasons, "sources": [source.model_dump(mode="json") for source in sources]}
    serialized = json.dumps(payload, sort_keys=True).lower()
    markers = ("ghp_", "github_pat_", "sk-", "token=", "bearer ")
    return not any(marker in serialized for marker in markers)
