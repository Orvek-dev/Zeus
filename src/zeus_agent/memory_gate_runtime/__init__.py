"""Memory write gate (P10, default-OFF) — was "ontology"/Demeter, re-aimed.

Honest framing: this is a provenance-pinned candidate→review→promote pipeline
for the agent's long-term memory, NOT a knowledge graph. As governance it is
strong: nothing an agent writes becomes durable context without promotion,
and content born in a tainted session can never be promoted at all
(anti-poisoning) — memory is the one place an injection outlives the session.
"""

from __future__ import annotations

from .gate import MemoryCandidate, MemoryWriteGate

__all__ = ["MemoryCandidate", "MemoryWriteGate"]
