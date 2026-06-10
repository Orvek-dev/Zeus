"""Graded approval (M5) — the human surface of earned autonomy.

Approval is not yes/no but: approve once · approve for this session (a scoped,
expiring grant) · approve a narrower scope · reject with an alternative. A
standing grant can never cover a hard-risk action — those always re-prompt.
"""

from __future__ import annotations

from .grants import (
    ApprovalGrant,
    GrantScope,
    GrantStore,
    grant_covers,
    issue_grant,
)

__all__ = ["ApprovalGrant", "GrantScope", "GrantStore", "grant_covers", "issue_grant"]
