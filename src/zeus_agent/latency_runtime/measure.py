from __future__ import annotations

import time
from dataclasses import dataclass

from pydantic import JsonValue

from zeus_agent.decision_api_runtime import (
    DecisionContext,
    DecisionRequest,
    GateSurface,
    HostKind,
    ZeusDecisionEngine,
)


@dataclass(frozen=True, slots=True)
class LatencyReport:
    samples: int
    decision_p50_ms: float
    decision_p95_ms: float
    budget_p95_ms: float
    daemon_recommended: bool

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "samples": self.samples,
            "decision_p50_ms": self.decision_p50_ms,
            "decision_p95_ms": self.decision_p95_ms,
            "budget_p95_ms": self.budget_p95_ms,
            "daemon_recommended": self.daemon_recommended,
        }


def measure_decision_latency(
    engine: ZeusDecisionEngine,
    *,
    samples: int,
    budget_p95_ms: float = 50.0,
) -> LatencyReport:
    count = max(samples, 1)
    durations = []
    for index in range(count):
        request = DecisionRequest(
            principal_id="operator.latency",
            session_id="latency.session",
            run_id="run.latency.{0}".format(index),
            capability_id="fs.read",
            context=DecisionContext(host=HostKind.console, surface=GateSurface.console),
        )
        start = time.perf_counter_ns()
        engine.decide(request)
        durations.append((time.perf_counter_ns() - start) / 1_000_000)
    ordered = sorted(durations)
    p50 = _percentile(ordered, 0.50)
    p95 = _percentile(ordered, 0.95)
    return LatencyReport(
        samples=count,
        decision_p50_ms=round(p50, 3),
        decision_p95_ms=round(p95, 3),
        budget_p95_ms=budget_p95_ms,
        daemon_recommended=p95 > budget_p95_ms,
    )


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    index = min(int((len(values) - 1) * quantile), len(values) - 1)
    return values[index]
