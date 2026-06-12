from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.memory_cockpit_runtime import MemoryCockpitRuntime
from zeus_agent.memory_entry_runtime import MemoryEntryRuntime


def register_wave44_commands(app: typer.Typer) -> None:
    @app.command("remember")
    def remember(
        home: Optional[Path] = typer.Option(None, "--home"),
        subject: Optional[str] = typer.Option(None, "--subject"),
        add: bool = typer.Option(False, "--add", help="Add a local memory fact candidate."),
        predicate: Optional[str] = typer.Option(None, "--predicate"),
        object_text: Optional[str] = typer.Option(None, "--object-text"),
        provenance_id: Optional[str] = typer.Option(None, "--provenance-id"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        state_home = home or default_zeus_home()
        if add:
            runtime = MemoryEntryRuntime(state_home)
            if subject is None or predicate is None or object_text is None or provenance_id is None:
                _print_payload(runtime.block("missing_memory_fields").to_payload(), as_json=as_json)
                return
            result = runtime.add(
                subject=subject,
                predicate=predicate,
                object_text=object_text,
                provenance_id=provenance_id,
            )
            _print_payload(result.to_payload(), as_json=as_json)
            return
        result = MemoryCockpitRuntime(state_home).build(subject=subject)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
