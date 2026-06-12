from __future__ import annotations

from zeus_agent.wallet_runtime import CostMeter, PriceTable, TokenPrice


def test_units_are_integer_microusd() -> None:
    meter = CostMeter()
    assert meter.units("claude-fable-5", prompt_tokens=1_000, completion_tokens=1_000) == 30_000
    # ceil, never floor: 1 token of output still costs a unit
    assert meter.units("claude-fable-5", prompt_tokens=0, completion_tokens=1) == 25


def test_unknown_model_costs_conservative_default() -> None:
    meter = CostMeter(
        PriceTable(prices={}, default=TokenPrice(input_per_1k=7, output_per_1k=11))
    )
    assert meter.units("totally-new-model", prompt_tokens=1_000, completion_tokens=1_000) == 18


def test_estimate_counts_messages_tools_and_max_tokens() -> None:
    meter = CostMeter()
    small = meter.estimate_request_units(
        {"model": "claude-fable-5", "messages": [{"role": "user", "content": "hi"}]}
    )
    bigger_prompt = meter.estimate_request_units(
        {"model": "claude-fable-5", "messages": [{"role": "user", "content": "hi" * 4_000}]}
    )
    capped_output = meter.estimate_request_units(
        {
            "model": "claude-fable-5",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 10,
        }
    )
    assert bigger_prompt > small
    assert capped_output < small  # declared max_tokens shrinks the estimate
    assert small > 0


def test_actual_units_accepts_both_usage_dialects() -> None:
    meter = CostMeter()
    chat = meter.actual_units("claude-fable-5", {"prompt_tokens": 100, "completion_tokens": 100})
    responses = meter.actual_units("claude-fable-5", {"input_tokens": 100, "output_tokens": 100})
    assert chat == responses == 3_000
    assert meter.actual_units("claude-fable-5", {}) == 0
