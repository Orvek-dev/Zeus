"""Least-authority compiler (P1): objective frame → AuthorityEnvelope.

Eight steps: intent parse (LLM boundary, reused) · capability resolution ·
dependency-closure provenance · in-envelope risk partition · explicit lock
list · taint overlay · VoI questions · burn-after-use + usage shrink. The
envelope, not a chat approval, is what the Decision API enforces per action.
"""

from __future__ import annotations

from .attenuation import authority_context_from, derive_child_authority
from .compiler import (
    CompileResult,
    ExcludedCapability,
    ShrinkProposal,
    compile_envelope,
    shrink_proposal,
)
from .sqlite_store import SQLiteEnvelopeStore
from .models import (
    AuthorityEnvelope,
    CapabilityRequest,
    EnvelopeStore,
    GrantTier,
    GrantedCapability,
    LockedCapability,
    VoiQuestion,
)

__all__ = [
    "AuthorityEnvelope",
    "SQLiteEnvelopeStore",
    "CapabilityRequest",
    "CompileResult",
    "EnvelopeStore",
    "ExcludedCapability",
    "GrantTier",
    "GrantedCapability",
    "LockedCapability",
    "ShrinkProposal",
    "VoiQuestion",
    "authority_context_from",
    "compile_envelope",
    "derive_child_authority",
    "shrink_proposal",
]
