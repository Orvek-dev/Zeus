"""zeusd — the long-lived local control-plane daemon surface (P5).

One process, three gates: the LLM proxy (Gate 1), the /zeus/* Decision API
for remote hooks (Gate 3 over HTTP, pairing-gated), and the session-recovery
briefing. Hosts that can call a blocking hook POST here; hosts that cannot
are caught at the proxy.
"""

from __future__ import annotations

from .api import ZeusApiSurface

__all__ = ["ZeusApiSurface"]
