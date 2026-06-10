from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from zeus_agent.decision_api_runtime import ZeusDecisionEngine
from zeus_agent.graded_approval_runtime import ApprovalGrant, GrantStore
from zeus_agent.taint_runtime import SessionTaintTracker, TaintLabel
from zeus_agent.trust_loop_runtime import (
    FlightRecorder,
    SQLiteEvidenceLedger,
    SQLiteTrustStatStore,
)

from .mapping import seed_capability_store


class ControlPlaneState:
    """Durable control-plane state under ``<home>/control-plane``.

    A hook process lives for one decision, so everything that must outlive it
    (ledger, trust counts, session taint, standing grants, pending receipts)
    is file-backed here. Governors stay in-process — they protect loops inside
    one engine lifetime.
    """

    def __init__(self, home: Path) -> None:
        self.root = home / "control-plane"
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.root / "ledger.sqlite3"
        self.trust_path = self.root / "trust.sqlite3"
        self.taint_path = self.root / "taint.json"
        self.grants_path = self.root / "grants.json"
        self.pending_path = self.root / "pending.json"

    # ----------------------------------------------------------------- engine
    def build_engine(self) -> ZeusDecisionEngine:
        recorder = FlightRecorder(SQLiteEvidenceLedger(self.ledger_path))
        engine = ZeusDecisionEngine(
            recorder=recorder,
            capabilities=seed_capability_store(),
            taint=self.load_taint(),
            grants=self.load_grants(),
            trust_stats=SQLiteTrustStatStore(self.trust_path),
        )
        return engine

    # ------------------------------------------------------------------ taint
    def load_taint(self) -> SessionTaintTracker:
        tracker = SessionTaintTracker()
        for session_id, stamps in self._read_json(self.taint_path, {}).items():
            for item in stamps:
                if not isinstance(item, list) or len(item) != 2:
                    continue
                try:
                    tracker.stamp(session_id, TaintLabel(str(item[0])), str(item[1]))
                except ValueError:
                    continue
        return tracker

    def save_taint(self, tracker: SessionTaintTracker, session_ids: tuple[str, ...]) -> None:
        data = self._read_json(self.taint_path, {})
        for session_id in session_ids:
            data[session_id] = [
                [stamp.label.value, stamp.provenance] for stamp in tracker.stamps(session_id)
            ]
        self._write_json(self.taint_path, data)

    # ----------------------------------------------------------------- grants
    def load_grants(self) -> GrantStore:
        store = GrantStore()
        for raw in self._read_json(self.grants_path, []):
            try:
                store.add(ApprovalGrant.model_validate(raw))
            except ValueError:
                continue
        return store

    def add_grant(self, grant: ApprovalGrant) -> None:
        data = self._read_json(self.grants_path, [])
        data.append(grant.model_dump(mode="json"))
        self._write_json(self.grants_path, data)

    def save_grants(self, store: GrantStore) -> None:
        data = [grant.model_dump(mode="json") for grant in store.all()]
        self._write_json(self.grants_path, data)

    # --------------------------------------------------------------- pendings
    def push_pending(self, fingerprint: str, receipt_id: str) -> None:
        data = self._read_json(self.pending_path, {})
        data[fingerprint] = receipt_id
        self._write_json(self.pending_path, data)

    def pop_pending(self, fingerprint: str) -> Optional[str]:
        data = self._read_json(self.pending_path, {})
        receipt = data.pop(fingerprint, None)
        self._write_json(self.pending_path, data)
        return receipt if isinstance(receipt, str) else None

    # ------------------------------------------------------------------ files
    def _read_json(self, path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default

    def _write_json(self, path: Path, data) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
