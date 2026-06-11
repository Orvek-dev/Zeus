from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from zeus_agent.trust_loop_runtime import FlightRecorder

# Cost units across the control plane are integer micro-USD (1_000_000 = $1).
# Budgets, governor charges, and receipts all speak this unit so a wallet
# number is never a float and never ambiguous.


class TokenPrice(BaseModel):
    """Micro-USD per 1K tokens, split by direction."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    input_per_1k: int = Field(ge=0)
    output_per_1k: int = Field(ge=0)


class PriceTable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    prices: dict[str, TokenPrice] = Field(default_factory=dict)
    # Unknown models cost the conservative default — never free.
    default: TokenPrice

    def for_model(self, model: str) -> TokenPrice:
        return self.prices.get(model, self.default)


DEFAULT_PRICE_TABLE = PriceTable(
    prices={
        "claude-fable-5": TokenPrice(input_per_1k=5_000, output_per_1k=25_000),
        "claude-opus-4-8": TokenPrice(input_per_1k=15_000, output_per_1k=75_000),
        "claude-sonnet-4-6": TokenPrice(input_per_1k=3_000, output_per_1k=15_000),
        "claude-haiku-4-5": TokenPrice(input_per_1k=1_000, output_per_1k=5_000),
        "gpt-5.4": TokenPrice(input_per_1k=10_000, output_per_1k=40_000),
    },
    default=TokenPrice(input_per_1k=10_000, output_per_1k=40_000),
)

_CHARS_PER_TOKEN = 4
_DEFAULT_COMPLETION_TOKENS = 512


class CostMeter:
    """Token×price metering for the LLM proxy gate.

    Estimates are deliberately rough (chars/4) but deterministic — they exist
    to make the PRE-CALL budget check enforceable, not to bill. Actuals come
    from the provider's usage block and are what the ledger charges.
    """

    def __init__(self, table: PriceTable = DEFAULT_PRICE_TABLE) -> None:
        self.table = table

    def units(self, model: str, *, prompt_tokens: int, completion_tokens: int) -> int:
        price = self.table.for_model(model)
        prompt_cost = math.ceil(max(prompt_tokens, 0) * price.input_per_1k / 1000)
        completion_cost = math.ceil(max(completion_tokens, 0) * price.output_per_1k / 1000)
        return prompt_cost + completion_cost

    def estimate_request_units(self, body: dict[str, JsonValue]) -> int:
        model = str(body.get("model", ""))
        prompt_tokens = max(1, math.ceil(_prompt_chars(body) / _CHARS_PER_TOKEN))
        raw_max = body.get("max_tokens", body.get("max_output_tokens"))
        completion_tokens = (
            int(raw_max) if isinstance(raw_max, (int, float)) and int(raw_max) > 0
            else _DEFAULT_COMPLETION_TOKENS
        )
        return self.units(model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)

    def actual_units(self, model: str, usage: dict[str, JsonValue]) -> int:
        prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
        return self.units(
            model,
            prompt_tokens=int(prompt) if isinstance(prompt, (int, float)) else 0,
            completion_tokens=int(completion) if isinstance(completion, (int, float)) else 0,
        )


class QuotaSwitchRule(BaseModel):
    """Policy, not routing: when the watched budget runs low, the proxy may
    rewrite the request to a PRE-APPROVED alternate model. The rewrite itself
    is a governed decision with its own receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    watch_model: str
    residual_pct_below: float = Field(gt=0, le=100)
    switch_to: str


class WalletPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    rules: tuple[QuotaSwitchRule, ...] = ()

    def rule_for(self, model: str) -> Optional[QuotaSwitchRule]:
        for rule in self.rules:
            if rule.watch_model == model:
                return rule
        return None


def weekly_spend_digest(
    recorder: FlightRecorder,
    *,
    now: datetime,
    days: int = 7,
) -> dict[str, JsonValue]:
    """Aggregate costed outcomes by objective and model over the window.

    Joins each execution outcome to its decision receipt via caused_by, so
    attribution uses what was DECIDED (objective, model arg), not what the
    outcome happens to mention.
    """
    cutoff = now - timedelta(days=days)
    total = 0
    requests = 0
    by_objective: dict[str, int] = {}
    by_model: dict[str, int] = {}
    for record in recorder.ledger.records():
        if str(record["kind"]) != "execution_outcome":
            continue
        payload = _payload_of(record)
        cost = payload.get("cost_actual_units", 0)
        if not isinstance(cost, (int, float)) or cost <= 0:
            continue
        created_at = _created_at(record)
        if created_at is None or created_at < cutoff:
            continue
        caused_by = payload.get("caused_by")
        decision_payload: dict[str, JsonValue] = {}
        if isinstance(caused_by, list) and caused_by:
            decision = recorder.ledger.record_by_id(str(caused_by[0]))
            if decision is not None:
                decision_payload = _payload_of(decision)
        objective = str(decision_payload.get("objective_id") or "adhoc.objective")
        args = decision_payload.get("args")
        model = str(args.get("model")) if isinstance(args, dict) and args.get("model") else "unknown"
        total += int(cost)
        requests += 1
        by_objective[objective] = by_objective.get(objective, 0) + int(cost)
        by_model[model] = by_model.get(model, 0) + int(cost)
    return {
        "window_days": days,
        "total_units": total,
        "requests": requests,
        "by_objective": by_objective,
        "by_model": by_model,
    }


def _prompt_chars(body: dict[str, JsonValue]) -> int:
    chars = 0
    messages = body.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if isinstance(message, dict):
                chars += _content_chars(message.get("content"))
    for key in ("input", "instructions", "prompt", "system"):
        chars += _content_chars(body.get(key))
    tools = body.get("tools")
    if isinstance(tools, list):
        chars += len(json.dumps(tools, ensure_ascii=False))
    return chars


def _content_chars(content: JsonValue | None) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(_content_chars(item) for item in content)
    if isinstance(content, dict):
        return sum(_content_chars(value) for value in content.values())
    return 0


def _payload_of(record: dict[str, JsonValue]) -> dict[str, JsonValue]:
    try:
        payload = json.loads(str(record["payload_json"]))
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _created_at(record: dict[str, JsonValue]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(record["created_at"]))
    except ValueError:
        return None
