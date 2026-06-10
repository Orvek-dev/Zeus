from __future__ import annotations

from typing import Final, Iterable, Optional

from zeus_agent.capability_registry_runtime import CapabilityRecord, Provenance, SideEffectClass
from zeus_agent.trust_loop_runtime import TrustDecision

from .models import TaintAssessment, TaintLabel, TaintStamp, require_text

# Capability prefixes whose OUTPUT is authored by someone other than the
# principal. Reading through them stamps the session `untrusted`.
_UNTRUSTED_SOURCE_PREFIXES: Final[tuple[str, ...]] = (
    "web.",
    "http.",
    "browser.",
    "mcp.",
    "mail.read",
    "gateway.read",
    "search.",
)

# Capability prefixes that expose secret or personal material. Reading through
# them stamps the session `private`.
_PRIVATE_SOURCE_PREFIXES: Final[tuple[str, ...]] = (
    "secret.",
    "credential.",
    "vault.",
    "keychain.",
)

# Capability prefixes that send data out of the local machine. Used by
# trifecta rule 3 (credential access + external send in the same turn).
_EXTERNAL_SEND_PREFIXES: Final[tuple[str, ...]] = (
    "mail.send",
    "gateway.",
    "vcs.push",
    "web.post",
    "http.post",
    "mcp.",
)

_SIDE_EFFECT_SENSITIVE: Final[frozenset[SideEffectClass]] = frozenset(
    {SideEffectClass.account_write, SideEffectClass.public_write}
)


def is_untrusted_source(capability_id: str, record: Optional[CapabilityRecord] = None) -> bool:
    """Does reading through this capability ingest foreign-authored data?

    MCP-imported tools are foreign by provenance regardless of their id; the
    rest is decided by a deterministic prefix table, never by an LLM.
    """
    if record is not None and record.provenance is Provenance.mcp:
        return True
    return capability_id.startswith(_UNTRUSTED_SOURCE_PREFIXES)


def is_private_source(capability_id: str) -> bool:
    return capability_id.startswith(_PRIVATE_SOURCE_PREFIXES)


def is_external_send(capability_id: str, *, network_host: Optional[str] = None) -> bool:
    if network_host is not None:
        return True
    return capability_id.startswith(_EXTERNAL_SEND_PREFIXES)


class SessionTaintTracker:
    """Per-session label set; labels persist until explicit sanitization.

    The tracker is the WRITE side of the taint engine: gates report what a
    session touched, the trifecta predicates below are the READ side that
    decide() consults before every action.
    """

    def __init__(self) -> None:
        self._stamps: dict[str, dict[tuple[str, str], TaintStamp]] = {}

    def stamp(self, session_id: str, label: TaintLabel, provenance: str) -> TaintStamp:
        session = require_text(session_id, "session_id")
        stamp = TaintStamp(label=label, provenance=provenance)
        self._stamps.setdefault(session, {})[(stamp.label.value, stamp.provenance)] = stamp
        return stamp

    def observe_capability(
        self,
        session_id: str,
        capability_id: str,
        *,
        record: Optional[CapabilityRecord] = None,
    ) -> tuple[TaintStamp, ...]:
        """Stamp the labels a completed capability call introduces."""
        capability = require_text(capability_id, "capability_id")
        stamped: list[TaintStamp] = []
        if is_untrusted_source(capability, record):
            stamped.append(self.stamp(session_id, TaintLabel.untrusted, capability))
        if is_private_source(capability):
            stamped.append(self.stamp(session_id, TaintLabel.private, capability))
        return tuple(stamped)

    def stamp_ledger_read(self, session_id: str, record_id: str) -> TaintStamp:
        """Anti-Goodhart rule: the agent's own ledger view is untrusted input.

        An agent that reads its trust thresholds cannot silently act on them —
        the read itself re-taints the session, forcing the sensitive-sink
        predicates back on.
        """
        return self.stamp(
            session_id,
            TaintLabel.untrusted,
            "ledger_read:{0}".format(require_text(record_id, "record_id")),
        )

    def labels(self, session_id: str) -> frozenset[TaintLabel]:
        return frozenset(stamp.label for stamp in self.stamps(session_id))

    def stamps(self, session_id: str) -> tuple[TaintStamp, ...]:
        session = self._stamps.get(session_id.strip(), {})
        return tuple(session.values())

    def sanitize(self, session_id: str, label: Optional[TaintLabel] = None) -> int:
        """Clear labels (all, or one kind) after a human-reviewed boundary."""
        session = self._stamps.get(session_id.strip())
        if session is None:
            return 0
        if label is None:
            removed = len(session)
            session.clear()
            return removed
        keys = [key for key, stamp in session.items() if stamp.label is label]
        for key in keys:
            del session[key]
        return len(keys)


def assess_action(
    *,
    live_labels: Iterable[TaintLabel],
    side_effect: SideEffectClass,
    network_host: Optional[str] = None,
    approved_hosts: Iterable[str] = (),
    credential_access: bool = False,
    external_send: bool = False,
) -> TaintAssessment:
    """Run the three lethal-trifecta predicates for one pending action.

    1. ``untrusted`` live AND account/public write → force ASK.
    2. ``private`` live AND target host outside the approved set → DENY (exfil).
    3. credential access + external send in the same turn → escalate one tier.
    """
    labels = frozenset(live_labels)
    approved = frozenset(host.strip() for host in approved_hosts if host.strip())
    reasons: list[str] = []
    forced: Optional[TrustDecision] = None
    escalation = 0

    untrusted_live = TaintLabel.untrusted in labels
    private_live = TaintLabel.private in labels
    sensitive_sink = side_effect in _SIDE_EFFECT_SENSITIVE

    if private_live and network_host is not None and network_host not in approved:
        forced = TrustDecision.DENY
        reasons.append("private_taint_to_unapproved_host")
    elif untrusted_live and sensitive_sink:
        forced = TrustDecision.ASK
        reasons.append("untrusted_taint_reaches_external_sink")

    if credential_access and external_send:
        escalation = 1
        reasons.append("credential_access_with_external_send")

    return TaintAssessment(
        tainted=untrusted_live or private_live,
        taint_sensitive=sensitive_sink or network_host is not None,
        forced_decision=forced,
        risk_escalation=escalation,
        reasons=tuple(reasons),
    )
