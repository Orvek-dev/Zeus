from __future__ import annotations

import typer


def register_dev_commands(app: typer.Typer) -> None:
    @app.command(
        "dev",
        context_settings={
            "allow_extra_args": True,
            "ignore_unknown_options": True,
            "help_option_names": [],
        },
        help="Legacy platform surface and the demoted executor (conformance harness).",
    )
    def dev(ctx: typer.Context) -> None:
        from typer.main import get_command

        from zeus_agent.cli import app as legacy_app

        command = get_command(legacy_app)
        command.main(args=list(ctx.args), prog_name="zeus dev", standalone_mode=True)
