from __future__ import annotations

from typer.testing import CliRunner

from zeus_agent import __version__
from zeus_agent.cli import app

runner = CliRunner()


def test_version_flag_reports_installed_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout
    assert "zeus-agent" in result.stdout


def test_version_matches_package_metadata() -> None:
    # The single source of truth: __init__.__version__ must equal what the CLI prints.
    result = runner.invoke(app, ["--version"])
    assert result.stdout.strip() == "zeus-agent {0}".format(__version__)


def test_commands_still_run_under_new_callback() -> None:
    result = runner.invoke(app, ["kernel-status"])
    assert result.exit_code == 0
    assert "kernel" in result.stdout.lower()
