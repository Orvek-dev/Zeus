from __future__ import annotations

from typing import Sequence

from pydantic import JsonValue

from zeus_agent.objective_runtime import ObjectiveCompiler
from zeus_agent.security.credentials import redact_secret_spans

JsonObject = dict[str, JsonValue]


def run_objective_batch(*, batch_id: str, objectives: Sequence[str]) -> JsonObject:
    compiler = ObjectiveCompiler()
    items = [compiler.compile(objective).model_dump(mode="json") for objective in objectives]
    compiled_count = len([item for item in items if item["status"] == "compiled"])
    blocked_count = len([item for item in items if item["status"] == "blocked"])
    return {
        "batch_id": redact_secret_spans(batch_id.strip()),
        "item_count": len(items),
        "compiled_count": compiled_count,
        "blocked_count": blocked_count,
        "items": items,
        "handler_executed": False,
        "network_opened": False,
        "live_production_claimed": False,
    }
