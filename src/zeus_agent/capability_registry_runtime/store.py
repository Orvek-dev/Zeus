from __future__ import annotations

from typing import Iterable, Optional

from .models import CapabilityRecord, VerbClass


class CapabilityStore:
    """In-memory capability table keyed by capability_id.

    The registry functions stay pure; this store is the lookup surface the
    Decision API (record per decision) and the authority compiler (sibling
    enumeration for lock lists) share.
    """

    def __init__(self, records: Iterable[CapabilityRecord] = ()) -> None:
        self._records: dict[str, CapabilityRecord] = {}
        for record in records:
            self.register(record)

    def register(self, record: CapabilityRecord) -> None:
        self._records[record.capability_id] = record

    def get(self, capability_id: str) -> Optional[CapabilityRecord]:
        return self._records.get(capability_id.strip())

    def records(self) -> tuple[CapabilityRecord, ...]:
        return tuple(self._records.values())

    def siblings_by_verb(self, verb_class: VerbClass) -> tuple[CapabilityRecord, ...]:
        return tuple(
            record for record in self._records.values() if record.verb_class is verb_class
        )
