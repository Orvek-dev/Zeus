from __future__ import annotations

import typer

from zeus_agent.cli_runtime import register_product_commands

app = typer.Typer(
    no_args_is_help=True,
    help=(
        "Zeus - a local-first governance control plane for AI agents. "
        "Agent platforms plug in through gates; Zeus decides, records, and "
        "earns autonomy down to fewer asks."
    ),
)


def _version_callback(value: bool) -> None:
    if value:
        from zeus_agent import __version__

        typer.echo("zeus-agent {0}".format(__version__))
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the installed zeus-agent version and exit.",
    ),
) -> None:
    return None


register_product_commands(app)
