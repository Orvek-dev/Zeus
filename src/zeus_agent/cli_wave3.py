from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict, Optional

import typer

from zeus_agent.agent_runtime.surfaces import chat_wave3_surface, run_wave3_surface
from zeus_agent.entry_runtime import ZeusChatRuntime, default_zeus_home
from zeus_agent.eval.wave3 import run_wave3_eval


def register_wave3_commands(app: typer.Typer) -> None:
    @app.command("run")
    def wave3_run(
        prompt: str = typer.Option(..., "--prompt", help="Prompt for the fake Wave 3 run loop."),
        home: Optional[Path] = typer.Option(None, "--home", help="Local Wave 3 state home."),
        scenario: str = typer.Option("fake-read", "--scenario", help="Fake Wave 3 run scenario."),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        state_home = home if home is not None else Path(tempfile.mkdtemp(prefix="zeus-wave3-"))
        _print_payload(run_wave3_surface(prompt=prompt, home=state_home, scenario=scenario), as_json)

    @app.command("chat")
    def wave3_chat(
        message: str = typer.Option(..., "--message", help="Message for Zeus chat mode."),
        home: Optional[Path] = typer.Option(None, "--home", help="Local Zeus state home."),
        scenario: str = typer.Option(
            "zeus-chat",
            "--scenario",
            help="Chat scenario. Use zeus-chat for the product chat surface or fake-search for the legacy Wave 3 loop.",
        ),
        session_id: str = typer.Option("default", "--session-id", help="Session id for Zeus chat mode."),
        provider_id: Optional[str] = typer.Option(None, "--provider-id", help="Provider id for Zeus chat mode."),
        profile: str = typer.Option("chat", "--profile", help="Zeus user-facing profile."),
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        state_home = home if home is not None else default_zeus_home()
        if scenario == "fake-search":
            _print_payload(chat_wave3_surface(message=message, home=state_home, scenario=scenario), as_json)
            return
        if scenario != "zeus-chat":
            raise typer.BadParameter("scenario must be one of: zeus-chat, fake-search")
        payload = ZeusChatRuntime(state_home).run_turn(
            message=message,
            session_id=session_id,
            provider_id=provider_id,
            profile=profile,
        ).to_payload()
        _print_payload(payload, as_json)

    @app.command("wave3-eval")
    def wave3_eval(
        as_json: bool = typer.Option(False, "--json", help="Print structured JSON output."),
    ) -> None:
        _print_payload(run_wave3_eval(), as_json)


def _print_payload(payload: Dict[str, object], as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
