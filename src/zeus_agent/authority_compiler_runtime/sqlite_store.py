from __future__ import annotations

from datetime import datetime
from typing import Optional

from zeus_agent.trust_loop_runtime.state_store import SQLiteControlPlaneStore

from .models import AuthorityEnvelope, EnvelopeStore


class SQLiteEnvelopeStore(EnvelopeStore):
    """Envelopes over the shared control-plane store.

    Resolves the v2 open question (new SQLite table, not ObjectiveRunStore):
    an envelope compiled in one process must bind every gate process that
    later decides under the same objective.
    """

    def __init__(self, store: SQLiteControlPlaneStore) -> None:
        self._store = store

    def put(self, envelope: AuthorityEnvelope) -> None:
        self._store.envelope_save(envelope.objective_id, envelope.model_dump_json())

    def active_for(
        self,
        objective_id: Optional[str],
        *,
        now: Optional[datetime] = None,
    ) -> Optional[AuthorityEnvelope]:
        if objective_id is None:
            return None
        raw = self._store.envelope_get(objective_id)
        if raw is None:
            return None
        try:
            envelope = AuthorityEnvelope.model_validate_json(raw)
        except ValueError:
            return None
        return None if envelope.expired(now) else envelope

    def burn(self, objective_id: str, capability_id: str) -> Optional[AuthorityEnvelope]:
        envelope = self.active_for(objective_id)
        if envelope is None:
            return None
        granted = tuple(
            grant.model_copy(update={"burned": True})
            if grant.capability_id == capability_id
            else grant
            for grant in envelope.granted
        )
        updated = envelope.model_copy(update={"granted": granted})
        self.put(updated)
        return updated
