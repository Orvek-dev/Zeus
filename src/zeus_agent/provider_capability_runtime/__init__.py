"""Canonical provider capability handler.

One entry point for every provider call — fake, local, openai, anthropic —
replacing the 3+ parallel provider paths (entry_runtime trust-loop call,
live_provider_execution registry path, model_runtime loopback path, and the
live_provider_*transport families). All vendors dispatch through the single
``GovernedExecutionDispatcher`` chokepoint; raw keys and non-allowlisted
models/endpoints are rejected before any socket opens.
"""

from __future__ import annotations

from .handler import CanonicalProviderHandler
from .models import ProviderReceipt, ProviderRequest, ProviderVendor

__all__ = [
    "CanonicalProviderHandler",
    "ProviderReceipt",
    "ProviderRequest",
    "ProviderVendor",
]
