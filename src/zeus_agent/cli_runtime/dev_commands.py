from __future__ import annotations

import typer

from .context import echo_json


def register_dev_commands(app: typer.Typer) -> None:
    @app.command(
        "dev",
        context_settings={
            "allow_extra_args": True,
            "ignore_unknown_options": True,
            "help_option_names": [],
        },
        help="Archived legacy harness notice.",
    )
    def dev(ctx: typer.Context) -> None:
        echo_json(
            {
                "archived": True,
                "requested_args": list(ctx.args),
                "reason": "legacy_surface_moved_to_attic",
                "path": "attic/legacy-wave",
                "next": "Use product commands from `zeus --help`; archived wave code is not packaged or in the default test suite.",
            }
        )
