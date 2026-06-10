"""Frame autonomy (M2): an utterance becomes a validated ObjectiveFrameInput.

The LLM fills the frame (GenerateFn seam); Zeus owns the deterministic parse,
fail-closed validation, and the safety pre-pass seed. Domain comprehension is
borrowed; structure stays owned. Pairs with objective_card_runtime (which
compiles the validated frame) and workflow_execution_runtime (which runs it).
"""

from __future__ import annotations

from .bridge import intent_seed
from .models import FrameParseResult
from .producer import GenerateFn, parse_frame, produce_frame, provider_generate

__all__ = [
    "FrameParseResult",
    "GenerateFn",
    "intent_seed",
    "parse_frame",
    "produce_frame",
    "provider_generate",
]
