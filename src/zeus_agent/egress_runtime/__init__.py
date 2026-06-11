"""Gate 4 — the egress/filesystem ring (P8): the non-cooperative-host defense.

Hooks and proxies govern hosts that cooperate; the egress ring is what stands
when one doesn't. Network targets outside the allowlist and paths outside the
ring are DENIED regardless of what policy would have said, the credential
broker injects keys only at the egress point on an allowed decision (the
agent process never holds them), and every blocked attempt is evidence.

OS-level enforcement is delegated to Anthropic's sandbox-runtime (srt,
Apache-2.0): Zeus EMITS the srt profile and serves the decisions; srt wraps
the agent process. Zeus copies no srt code.
"""

from __future__ import annotations

from .gate import EgressGate, EgressRequest, EgressResult, EgressRing, StaticVault
from .profile import build_srt_profile

__all__ = [
    "EgressGate",
    "EgressRequest",
    "EgressResult",
    "EgressRing",
    "StaticVault",
    "build_srt_profile",
]
