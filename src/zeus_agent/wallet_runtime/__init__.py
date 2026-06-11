"""Wallet — per-objective cost attribution and pre-call budget truth (P3).

The proxy meters every model call in integer micro-USD, charges the governor
budget through ``record()``, and answers "where did the money go" from the
ledger, not from provider dashboards.
"""

from __future__ import annotations

from .meter import (
    DEFAULT_PRICE_TABLE,
    CostMeter,
    PriceTable,
    QuotaSwitchRule,
    TokenPrice,
    WalletPolicy,
    weekly_spend_digest,
)

__all__ = [
    "CostMeter",
    "DEFAULT_PRICE_TABLE",
    "PriceTable",
    "QuotaSwitchRule",
    "TokenPrice",
    "WalletPolicy",
    "weekly_spend_digest",
]
