from __future__ import annotations

import json
from typing import Optional, Sequence
from urllib.parse import urlparse

from zeus_agent.live_research_adapter_catalog_runtime import live_research_adapter_catalog
from zeus_agent.live_research_adapter_catalog_runtime.models import LiveResearchAdapterSpec
from zeus_agent.live_research_source_config_runtime.models import LiveResearchSourceConfigResult
from zeus_agent.security.credentials import redact_secret_spans


class LiveResearchSourceConfigRuntime:
    def configure(
        self,
        *,
        adapter_id: str,
        endpoint: Optional[str] = None,
        allow_loopback_smoke: bool = False,
    ) -> LiveResearchSourceConfigResult:
        safe_adapter_id = redact_secret_spans(adapter_id)
        adapter = _adapter_by_id(safe_adapter_id)
        if adapter is None:
            return _blocked(
                adapter_id=safe_adapter_id,
                source_id=None,
                endpoint=None,
                reasons=("live_research_adapter_unknown",),
            )
        return _build_config(
            adapter=adapter,
            endpoint=endpoint,
            allow_loopback_smoke=allow_loopback_smoke,
        )


def _adapter_by_id(adapter_id: str) -> Optional[LiveResearchAdapterSpec]:
    for adapter in live_research_adapter_catalog():
        if adapter.adapter_id == adapter_id:
            return adapter
    return None


def _build_config(
    *,
    adapter: LiveResearchAdapterSpec,
    endpoint: Optional[str],
    allow_loopback_smoke: bool,
) -> LiveResearchSourceConfigResult:
    safe_endpoint = None if endpoint is None else redact_secret_spans(endpoint)
    default_endpoint_used = endpoint is None and adapter.default_endpoint is not None
    selected_endpoint = adapter.default_endpoint if default_endpoint_used else safe_endpoint
    reasons = _blocked_reasons(
        adapter=adapter,
        raw_endpoint=endpoint,
        selected_endpoint=selected_endpoint,
        allow_loopback_smoke=allow_loopback_smoke,
    )
    loopback = _is_loopback(selected_endpoint)
    return LiveResearchSourceConfigResult(
        decision="blocked" if reasons else "configured",
        config_id=None if reasons else "live-research-source-config://{0}".format(adapter.adapter_id),
        adapter_id=adapter.adapter_id,
        source_id=adapter.source_id,
        endpoint=selected_endpoint,
        default_endpoint_used=default_endpoint_used,
        endpoint_config_required=adapter.endpoint_config_required,
        adapter_bound=True,
        endpoint_bound=selected_endpoint is not None,
        loopback_endpoint=loopback,
        non_loopback_endpoint=selected_endpoint is not None and not loopback,
        credential_scope=adapter.credential_scope,
        real_fetcher_available=adapter.real_fetcher_available,
        production_fetcher_configured=adapter.production_fetcher_configured,
        blocked_reasons=tuple(dict.fromkeys(reasons)),
        no_secret_echo=_no_secret_echo(selected_endpoint, reasons),
    )


def _blocked_reasons(
    *,
    adapter: LiveResearchAdapterSpec,
    raw_endpoint: Optional[str],
    selected_endpoint: Optional[str],
    allow_loopback_smoke: bool,
) -> list[str]:
    reasons: list[str] = []
    if selected_endpoint is None and adapter.endpoint_config_required:
        reasons.append("live_research_endpoint_required")
    if raw_endpoint is not None and redact_secret_spans(raw_endpoint) != raw_endpoint:
        reasons.append("live_research_endpoint_contains_secret")
    if selected_endpoint is not None and _scheme_invalid(selected_endpoint):
        reasons.append("live_research_endpoint_scheme_invalid")
    if selected_endpoint is not None and _is_loopback(selected_endpoint) and not allow_loopback_smoke:
        reasons.append("live_research_loopback_endpoint_requires_smoke_flag")
    return reasons


def _scheme_invalid(endpoint: str) -> bool:
    parsed = urlparse(endpoint)
    if parsed.scheme == "https":
        return False
    return not (parsed.scheme == "http" and _is_loopback(endpoint))


def _is_loopback(endpoint: Optional[str]) -> bool:
    if endpoint is None:
        return False
    host = urlparse(endpoint).hostname
    return host in {"127.0.0.1", "localhost", "::1"} if host is not None else False


def _blocked(
    *,
    adapter_id: str,
    source_id: Optional[str],
    endpoint: Optional[str],
    reasons: tuple[str, ...],
) -> LiveResearchSourceConfigResult:
    return LiveResearchSourceConfigResult(
        decision="blocked",
        config_id=None,
        adapter_id=adapter_id,
        source_id=source_id,
        endpoint=endpoint,
        blocked_reasons=reasons,
        no_secret_echo=_no_secret_echo(endpoint, reasons),
    )


def _no_secret_echo(endpoint: Optional[str], reasons: Sequence[str]) -> bool:
    payload = {"endpoint": endpoint, "blocked_reasons": list(reasons)}
    serialized = json.dumps(payload, sort_keys=True).lower()
    markers = ("ghp_", "github_pat_", "sk-", "token=", "bearer ")
    return not any(marker in serialized for marker in markers)
