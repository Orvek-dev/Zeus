from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class GrantScope(str, Enum):
    once = "once"
    session = "session"
    narrower = "narrower"


class ApprovalGrant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    grant_id: str
    capability_id: str
    scope: GrantScope
    session_id: Optional[str] = None
    narrowed_paths: tuple[str, ...] = ()
    expires_at_epoch: int = 0       # 0 = no expiry (used by 'once'); compared to 'now'
    covers_hard_risk: bool = False  # always False — a standing grant cannot cover hard risk
    consumed: bool = False


def issue_grant(
    *,
    grant_id: str,
    capability_id: str,
    scope: GrantScope,
    session_id: Optional[str] = None,
    narrowed_paths: tuple[str, ...] = (),
    expires_at_epoch: int = 0,
) -> ApprovalGrant:
    """Issue a graded grant. covers_hard_risk is forced False: a session/narrower
    grant can never pre-authorize a hard-risk action."""
    return ApprovalGrant(
        grant_id=grant_id,
        capability_id=capability_id,
        scope=scope,
        session_id=session_id,
        narrowed_paths=narrowed_paths,
        expires_at_epoch=expires_at_epoch,
        covers_hard_risk=False,
    )


def grant_covers(
    grant: ApprovalGrant,
    *,
    capability_id: str,
    now_epoch: int,
    session_id: Optional[str] = None,
    path: Optional[str] = None,
    hard_risk: bool = False,
) -> bool:
    """Does this grant authorize the action right now?

    A 'once' grant covers a single use (and is consumed). A 'session' grant
    covers the same session until it expires. A 'narrower' grant additionally
    requires the path to be inside the narrowed set. Hard-risk actions are NEVER
    covered by a standing grant.
    """
    if grant.consumed:
        return False
    if grant.capability_id != capability_id:
        return False
    if hard_risk:
        return False
    if grant.expires_at_epoch != 0 and now_epoch >= grant.expires_at_epoch:
        return False
    if grant.scope is GrantScope.once:
        return True
    if grant.scope is GrantScope.session:
        return session_id is not None and session_id == grant.session_id
    # narrower: same session (if set) and the path must be inside the narrowed set
    if grant.session_id is not None and session_id != grant.session_id:
        return False
    if path is None:
        return False
    return any(path == allowed or path.startswith(allowed.rstrip("/") + "/") for allowed in grant.narrowed_paths)
