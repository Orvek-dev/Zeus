from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from zeus_agent.capability_registry_runtime import CapabilityStore
from zeus_agent.decision_api_runtime import ZeusDecisionEngine
from zeus_agent.governor_runtime import GovernorBank, NoveltyGovernor
from zeus_agent.graded_approval_runtime import ApprovalGrant, GrantStore
from zeus_agent.taint_runtime import SessionTaintTracker, TaintLabel
from zeus_agent.trust_loop_runtime import (
    FlightRecorder,
    SQLiteApprovalQueue,
    SQLiteControlPlaneStore,
    SQLiteEvidenceLedger,
    SQLiteReplayAuthorizationStore,
    SQLiteTrustStatStore,
)

from .mapping import seed_capability_store


class ControlPlaneState:
    """Durable control-plane state under ``<home>/control-plane``.

    A hook process lives for one decision, so everything that must outlive it
    (ledger, trust counts, session taint, standing grants, pending receipts,
    budget counters, the approval queue, the decision sequence) is file-backed
    here. Only the rate/loop governors stay in-process: they guard a single
    engine's loop; cross-process loop governance is the P7 organ.
    """

    def __init__(self, home: Path) -> None:
        self.root = home / "control-plane"
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.root / "ledger.sqlite3"
        self.trust_path = self.root / "trust.sqlite3"
        self.state_path = self.root / "state.sqlite3"
        self.taint_path = self.root / "taint.json"
        self.grants_path = self.root / "grants.json"
        self.pending_path = self.root / "pending.json"

    # ----------------------------------------------------------------- engine
    def build_engine(self, *, capabilities: Optional[CapabilityStore] = None) -> ZeusDecisionEngine:
        """One control plane, many gates: every gate shares this home but
        brings its own static capability table (per-surface doctrine)."""
        from zeus_agent.authority_compiler_runtime import SQLiteEnvelopeStore
        from zeus_agent.capability_registry_runtime import CapabilityRecord
        from zeus_agent.consequence_runtime import explain

        recorder = FlightRecorder(SQLiteEvidenceLedger(self.ledger_path))
        store = SQLiteControlPlaneStore(self.state_path)
        capability_store = capabilities if capabilities is not None else seed_capability_store()
        # persisted records (policy-pack never-do locks, MCP/skill quarantine,
        # reviewed classifications) override the static seed at EVERY gate.
        for _capability_id, raw in store.capability_all():
            try:
                capability_store.register(CapabilityRecord.model_validate_json(raw))
            except ValueError:
                continue
        engine = ZeusDecisionEngine(
            recorder=recorder,
            capabilities=capability_store,
            envelopes=SQLiteEnvelopeStore(store),
            taint=self.load_taint(),
            governors=GovernorBank(
                _governor_config(store),
                budget_store=store,
                novelty=NoveltyGovernor(store),
                force_ask_reason=store.kv_get("governor.force_ask_reason") or None,
            ),
            grants=self.load_grants(),
            queue=SQLiteApprovalQueue(store),
            replay_authorizations=SQLiteReplayAuthorizationStore(store),
            trust_stats=SQLiteTrustStatStore(self.trust_path),
            self_protection_roots=self.self_protection_roots(),
            force_deny_reason=store.kv_get("operator.freeze_reason") or None,
            seq_counter=lambda: store.next_counter("decision_seq"),
            # explainable-or-escalated, enforced inside decide() so the receipt
            # is the truth — every gate built here inherits the rule.
            explainability=lambda record: explain(record) is not None,
        )
        return engine

    def self_protection_roots(self) -> tuple[Path, ...]:
        return (
            self.root,
            Path.home() / ".claude",
            Path.home() / ".hermes",
            Path.home() / ".openclaw",
        )

    def tripwire_paths(self) -> tuple[Path, ...]:
        return (
            self.ledger_path,
            self.state_path,
            self.trust_path,
            self.taint_path,
            self.grants_path,
            self.pending_path,
            self.root / "connect.json",
            self.root / "broker.json",
        )

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
        """A WRITE-THROUGH store: every gate process lives for one decision, so
        a grant burned in memory only (engine step 4b consume) would re-fire at
        the next process — "approve once" must mean once at EVERY gate, not
        just the one that remembered to persist."""
        store = _WriteThroughGrantStore(self.save_grants, self._load_grant_records)
        store.refresh()
        return store

    def add_grant(self, grant: ApprovalGrant) -> None:
        data = self._read_json(self.grants_path, [])
        data.append(grant.model_dump(mode="json"))
        self._write_json(self.grants_path, data)

    def save_grants(self, store: GrantStore) -> None:
        data = [grant.model_dump(mode="json") for grant in GrantStore.all(store)]
        self._write_json(self.grants_path, data)

    def _load_grant_records(self) -> tuple[ApprovalGrant, ...]:
        grants: list[ApprovalGrant] = []
        for raw in self._read_json(self.grants_path, []):
            try:
                grants.append(ApprovalGrant.model_validate(raw))
            except ValueError:
                continue
        return tuple(grants)

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
        return _read_json_file(path, default)

    def _write_json(self, path: Path, data) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class _WriteThroughGrantStore(GrantStore):
    """GrantStore that persists every mutation. `seed()` loads from disk
    without re-saving; `add()`/`consume()` write through immediately so a
    burned once-grant is dead for every later gate process."""

    def __init__(self, save, load) -> None:
        super().__init__()
        self._save = save
        self._load = load
        self._refreshing = False

    def refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        try:
            self._grants = {}
            for grant in self._load():
                super().add(grant)
        finally:
            self._refreshing = False

    def seed(self, grant: ApprovalGrant) -> None:
        super().add(grant)

    def add(self, grant: ApprovalGrant) -> None:
        self.refresh()
        super().add(grant)
        self._save(self)

    def get(self, grant_id: str) -> Optional[ApprovalGrant]:
        self.refresh()
        return super().get(grant_id)

    def all(self) -> tuple[ApprovalGrant, ...]:
        self.refresh()
        return super().all()

    def consume(self, grant_id: str) -> None:
        self.refresh()
        super().consume(grant_id)
        self._save(self)

    def covering(self, **kwargs) -> Optional[ApprovalGrant]:
        self.refresh()
        grant = super().covering(**kwargs)
        if grant is not None and kwargs.get("consume", True):
            self._save(self)
        return grant


def _governor_config(store: SQLiteControlPlaneStore):
    """Governor knobs set by policy packs / NL rules live in the kv table."""
    from zeus_agent.governor_runtime import GovernorBankConfig

    def _int_of(name: str, default: int) -> int:
        raw = store.kv_get(name)
        return int(raw) if raw is not None and raw.isdigit() and int(raw) > 0 else default

    defaults = GovernorBankConfig()
    return GovernorBankConfig(
        rate_max_calls=_int_of("governor.rate_max_calls", defaults.rate_max_calls),
        rate_window_seconds=_int_of("governor.rate_window_seconds", defaults.rate_window_seconds),
        loop_max_iterations=_int_of("governor.loop_max_iterations", defaults.loop_max_iterations),
        loop_no_progress_limit=_int_of(
            "governor.loop_no_progress_limit", defaults.loop_no_progress_limit
        ),
    )


def _read_json_file(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
