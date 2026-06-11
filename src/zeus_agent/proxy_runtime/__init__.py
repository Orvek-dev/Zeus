"""Gate 1 — the governed LLM proxy (P3).

The host points its model base_url here; Zeus decides at request ingress
(budget, 429 on an empty wallet) and at response egress (every tool_call the
model emits is decided before release; denied calls are stripped and replaced
with a block notice so the model re-plans). Streaming passes text deltas
through immediately and never releases a tool_call before its decision.
"""

from __future__ import annotations

from .engine import (
    KV_LAST_REQUEST_AT,
    KV_LAST_RESPONSE_AT,
    KV_SECRET_FINDINGS,
    LlmProxyEngine,
    ProxyHttpResult,
    ProxySession,
    StreamOutcome,
)
from .hygiene import KV_HYGIENE_MODE, HygieneMode, hygiene_mode_of
from .mapping import MappedToolCall, map_proxy_tool_call, seed_proxy_capability_store
from .server import make_proxy_handler, run_proxy_server, session_from_headers

__all__ = [
    "KV_HYGIENE_MODE",
    "KV_LAST_REQUEST_AT",
    "KV_LAST_RESPONSE_AT",
    "KV_SECRET_FINDINGS",
    "HygieneMode",
    "LlmProxyEngine",
    "MappedToolCall",
    "ProxyHttpResult",
    "ProxySession",
    "StreamOutcome",
    "hygiene_mode_of",
    "make_proxy_handler",
    "map_proxy_tool_call",
    "run_proxy_server",
    "seed_proxy_capability_store",
    "session_from_headers",
]
