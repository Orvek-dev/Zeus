from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from zeus_agent.trust_loop_runtime import SQLiteEvidenceLedger


def test_ledger_append_serializes_concurrent_writers(tmp_path: Path) -> None:
    ledger_path = tmp_path / "ledger.sqlite3"
    barrier = threading.Barrier(8)

    def append(index: int) -> int:
        barrier.wait(timeout=5)
        event = SQLiteEvidenceLedger(ledger_path).append(
            kind="decision_receipt",
            run_id="run.concurrent",
            payload={"index": index},
        )
        return event.seq

    with ThreadPoolExecutor(max_workers=8) as pool:
        seqs = list(pool.map(append, range(8)))

    assert sorted(seqs) == list(range(1, 9))
    assert SQLiteEvidenceLedger(ledger_path).verify_chain().ok is True
