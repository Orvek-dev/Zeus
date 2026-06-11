"""hermes-agent adapter (P5) — the cleanest host surface.

hermes' pre_tool_call hook is BLOCKING: the hook pack POSTs each tool call to
zeusd `/zeus/decide` (pairing-signed) and blocks on DENY / unresolved ASK.
base_url rides Gate 1 (LLM proxy); MCP rides Gate 2 (gateway); subagents are
attenuated child principals — out-of-envelope is DENY, not ASK.

NOTE: the tool→capability table below targets the hermes tool names pinned in
the design notes; re-verify against the pinned hermes version at integration
time (the conformance suite is the contract either way).
"""

from __future__ import annotations

from .connect import hermes_connect_bundle
from .gate import HermesGate
from .mapping import map_hermes_tool_call

__all__ = ["HermesGate", "hermes_connect_bundle", "map_hermes_tool_call"]
