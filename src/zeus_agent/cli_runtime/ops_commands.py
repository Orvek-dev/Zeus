from __future__ import annotations

from pathlib import Path

import typer

from .context import echo_json, state_for_home


def register_ops_commands(app: typer.Typer) -> None:
    @app.command("tripwire", help="Snapshot or check control-plane file hashes.")
    def tripwire(
        snapshot: bool = typer.Option(False, "--snapshot", help="Store current control-plane file hashes."),
        check: bool = typer.Option(False, "--check", help="Detect changes since the last snapshot."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.self_protection_runtime import check_tripwire, snapshot_tripwire
        from zeus_agent.trust_loop_runtime import (
            FlightRecorder,
            SQLiteControlPlaneStore,
            SQLiteEvidenceLedger,
        )

        if snapshot and check:
            raise typer.BadParameter("use either --snapshot or --check")
        state = state_for_home(home)
        store = SQLiteControlPlaneStore(state.state_path)
        paths = state.tripwire_paths()
        if snapshot or not check:
            echo_json({"tracked": snapshot_tripwire(store, paths), "mode": "snapshot"})
            return
        recorder = FlightRecorder(SQLiteEvidenceLedger(state.ledger_path))
        changes = check_tripwire(store, recorder, paths)
        echo_json({"changed": [change.to_payload() for change in changes]})

    @app.command("latency", help="Measure warm decision latency for the local engine.")
    def latency(
        samples: int = typer.Option(25, "--samples", min=1, max=200),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.latency_runtime import measure_decision_latency

        report = measure_decision_latency(state_for_home(home).build_engine(), samples=samples)
        echo_json(report.to_payload())

    @app.command("freeze", help="Deny new decisions until the operator releases the freeze.")
    def freeze(
        release: bool = typer.Option(False, "--release", help="Release the global operator freeze."),
        reason: str = typer.Option("operator_freeze", "--reason"),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.trust_loop_runtime import (
            FlightRecorder,
            SQLiteControlPlaneStore,
            SQLiteEvidenceLedger,
        )

        state = state_for_home(home)
        store = SQLiteControlPlaneStore(state.state_path)
        recorder = FlightRecorder(SQLiteEvidenceLedger(state.ledger_path))
        if release:
            store.kv_set("operator.freeze_reason", "")
            event = recorder.ledger.append(
                kind="operator_freeze",
                run_id="operator.freeze",
                payload={"active": False, "reason": reason},
            )
            echo_json({"active": False, "receipt_id": event.record_id})
            return
        store.kv_set("operator.freeze_reason", reason)
        event = recorder.ledger.append(
            kind="operator_freeze",
            run_id="operator.freeze",
            payload={"active": True, "reason": reason},
        )
        echo_json({"active": True, "reason": reason, "receipt_id": event.record_id})

    @app.command("import-permissions", help="Import reviewed host permission rules without raw secrets.")
    def import_permissions(
        host: str = typer.Argument(..., help="Host to import from: claude-code."),
        settings: Path = typer.Option(..., "--settings", exists=True),
    ) -> None:
        if host != "claude-code":
            raise typer.BadParameter("unsupported permission import host: {0}".format(host))
        from zeus_agent.permission_import_runtime import summarize_claude_code_settings

        echo_json(summarize_claude_code_settings(settings))
