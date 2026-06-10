from __future__ import annotations

import json

import typer

from zeus_agent import __version__
from zeus_agent.welcome_runtime import build_welcome, render_text


def register_welcome_commands(app: typer.Typer) -> None:
    @app.command("welcome")
    def welcome(as_json: bool = typer.Option(False, "--json")) -> None:
        """Show the Zeus launch screen (objective-first, governed, evidence-backed)."""
        screen = build_welcome(version="v{0}".format(__version__))
        if as_json:
            typer.echo(json.dumps(screen.to_payload()))
        else:
            typer.echo(render_text(screen))
