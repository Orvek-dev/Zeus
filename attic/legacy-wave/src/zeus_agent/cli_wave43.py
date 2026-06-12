from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.model_cockpit_runtime import ModelCockpitRuntime
from zeus_agent.model_settings_runtime import ModelSettingsRuntime


def register_wave43_commands(app: typer.Typer) -> None:
    @app.command("model")
    def model(
        provider_id: Optional[str] = typer.Option(None, "--provider-id"),
        set_provider: Optional[str] = typer.Option(None, "--set", help="Set local model preference, e.g. openrouter/qwen."),
        model_id: Optional[str] = typer.Option(None, "--model-id", help="Optional model id override for --set."),
        show_config: bool = typer.Option(False, "--show-config", help="Show local model preference instead of catalog cockpit."),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        runtime = ModelSettingsRuntime(home or default_zeus_home())
        if set_provider is not None:
            _print_payload(runtime.set(provider_ref=set_provider, model_id=model_id).to_payload(), as_json=as_json)
            return
        if show_config:
            _print_payload(runtime.show().to_payload(), as_json=as_json)
            return
        result = ModelCockpitRuntime().build(provider_id=provider_id)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
