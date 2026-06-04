from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from zeus_agent.model_runtime.interfaces import (
    ProviderRuntimeRequest,
    ProviderRuntimeResponse,
    ProviderUsage,
)
from zeus_agent.model_runtime.provider_registry import ProviderRegistry
from zeus_agent.model_runtime.provider_responses import blocked_provider_response
from zeus_agent.runtime_lease import RuntimeLease


def audit_summaries(db_path: Path) -> tuple[str, ...]:
    assert db_path.exists(), "expected audit database to exist"
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT summary FROM audit_log_events ORDER BY event_id").fetchall()
    return tuple(str(row[0]) for row in rows)


def tool_call_count(db_path: Path) -> int:
    assert db_path.exists(), "expected audit database to exist"
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM session_state_tool_calls").fetchone()
    return int(row[0])


class BlockingProviderRegistry(ProviderRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[ProviderRuntimeRequest] = []

    def generate(
        self,
        request: ProviderRuntimeRequest,
        lease: RuntimeLease | None,
        *,
        fallback_provider_kind: str | None = None,
        budget_required: int = 1,
        now: datetime | None = None,
    ) -> ProviderRuntimeResponse:
        del lease, fallback_provider_kind, budget_required, now
        self.requests.append(request)
        return blocked_provider_response(request, "provider_unavailable")


class FallbackProviderRegistry(ProviderRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[ProviderRuntimeRequest] = []

    def generate(
        self,
        request: ProviderRuntimeRequest,
        lease: RuntimeLease | None,
        *,
        fallback_provider_kind: str | None = None,
        budget_required: int = 1,
        now: datetime | None = None,
    ) -> ProviderRuntimeResponse:
        del lease, fallback_provider_kind, budget_required, now
        self.requests.append(request)
        if len(self.requests) == 1:
            return blocked_provider_response(request, "provider_unavailable")
        return selected_response(request, "wave15.provider.scripted.{0}".format(len(self.requests)))


class FinalBlockedNetworkProviderRegistry(ProviderRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[ProviderRuntimeRequest] = []

    def generate(
        self,
        request: ProviderRuntimeRequest,
        lease: RuntimeLease | None,
        *,
        fallback_provider_kind: str | None = None,
        budget_required: int = 1,
        now: datetime | None = None,
    ) -> ProviderRuntimeResponse:
        del lease, fallback_provider_kind, budget_required, now
        self.requests.append(request)
        if len(self.requests) == 1:
            return selected_response(
                request,
                "wave15.provider.networked-first",
                network_opened=True,
            )
        return blocked_provider_response(request, "provider_unavailable")


class FinalTransientProviderRegistry(ProviderRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[ProviderRuntimeRequest] = []

    def generate(
        self,
        request: ProviderRuntimeRequest,
        lease: RuntimeLease | None,
        *,
        fallback_provider_kind: str | None = None,
        budget_required: int = 1,
        now: datetime | None = None,
    ) -> ProviderRuntimeResponse:
        del lease, fallback_provider_kind, budget_required, now
        self.requests.append(request)
        if len(self.requests) == 2:
            return blocked_provider_response(request, "provider_unavailable")
        return selected_response(request, "wave15.provider.scripted.{0}".format(len(self.requests)))


def selected_response(
    request: ProviderRuntimeRequest,
    response_id: str,
    *,
    network_opened: bool = False,
) -> ProviderRuntimeResponse:
    return ProviderRuntimeResponse(
        decision="selected",
        provider_kind=request.provider_kind,
        provider_id=request.provider_id,
        model_id=request.model_id,
        response_id=response_id,
        content="scripted local provider response",
        usage=ProviderUsage(input_tokens=1, output_tokens=1, budget_units=1, latency_ms=0),
        network_opened=network_opened,
    )
