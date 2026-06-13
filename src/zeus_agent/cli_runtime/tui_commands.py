from __future__ import annotations

from enum import Enum
from pathlib import Path

import typer
from rich.console import Console

from .approval_resolution import latest_pending_parked_id, resolve_parked
from .context import state_for_home


class TuiAction(str, Enum):
    approve_once = "approve-once"
    remember = "remember"
    deny = "deny"


def register_tui_commands(app: typer.Typer) -> None:
    @app.command("tui", help="K9s-style local control tower for status and approvals.")
    def tui(
        once: bool = typer.Option(False, "--once", help="Render once and exit."),
        action: TuiAction | None = typer.Option(None, "--action", help="approve-once | remember | deny."),
        parked: str | None = typer.Option(None, "--parked", help="Parked action id for --action."),
        last: bool = typer.Option(False, "--last", help="Use newest pending parked ASK for --action."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        if action is not None:
            target = _target_parked(parked=parked, last=last, home=home)
            resolve_parked(
                target,
                deny=action is TuiAction.deny,
                confirm=True,
                narrow_path=None,
                remember=action is TuiAction.remember,
                remember_hours=8,
                home=home,
            )
            return
        _render_once(home=home)
        if once:
            return
        _loop(home=home)


def _target_parked(*, parked: str | None, last: bool, home: Path | None) -> str:
    if parked is not None and last:
        raise typer.BadParameter("use either --parked or --last, not both")
    if parked is not None:
        return parked
    if last:
        return latest_pending_parked_id(home=home)
    raise typer.BadParameter("--action requires --parked or --last")


def _render_once(*, home: Path | None) -> None:
    from zeus_agent.tui_runtime import build_snapshot, render_snapshot

    console = Console(color_system=None, force_terminal=False, width=120)
    render_snapshot(build_snapshot(state_for_home(home)), console)


def _loop(*, home: Path | None) -> None:
    while True:
        command = typer.prompt("zeus", default="r").strip().lower()
        if command in {"q", "quit", "exit"}:
            return
        if command in {"r", "refresh"}:
            _render_once(home=home)
            continue
        if command not in {"o", "a", "d"}:
            typer.echo("commands: o approve once, a remember, d deny, r refresh, q quit")
            continue
        parked = typer.prompt("parked")
        action = {
            "o": TuiAction.approve_once,
            "a": TuiAction.remember,
            "d": TuiAction.deny,
        }[command]
        resolve_parked(
            parked,
            deny=action is TuiAction.deny,
            confirm=True,
            narrow_path=None,
            remember=action is TuiAction.remember,
            remember_hours=8,
            home=home,
        )
