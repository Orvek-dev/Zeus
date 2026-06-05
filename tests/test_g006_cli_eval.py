from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from zeus_agent.cli import app
from typer.testing import CliRunner


def test_g006_eval_reports_no_failures() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["g006-eval", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["failed"] == 0
    assert payload["suite"] == "g006"


def test_g006_gateway_help_lists_server_command() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "g006-gateway-server" in result.stdout


def test_python3_can_import_zeus_agent_cli_without_g006_syntax_error() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    result = subprocess.run(
        [
            "/usr/bin/python3",
            "-c",
            (
                "import sys; "
                "import zeus_agent.cli; "
                "print(' '.join(name for name in ("
                "'zeus_agent.eval.g006', "
                "'zeus_agent.g006_gateway_scenarios', "
                "'zeus_agent.gateway_runtime.server'"
                ") if name in sys.modules))"
            ),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_g006_gateway_fail_closed_does_not_echo_secret_like_value() -> None:
    runner = CliRunner()
    secret_like = "sk-g006-cli-secret-value"

    result = runner.invoke(
        app,
        [
            "g006-gateway-fail-closed",
            "--secret-like",
            secret_like,
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert secret_like not in result.stdout
    assert "raw_secret_present" in result.stdout


def test_g006_gateway_server_rejects_public_bind() -> None:
    db_path = Path("/tmp/zeus-g006-cli-test.sqlite")

    try:
        from zeus_agent.gateway_runtime.server import (
            GatewayLoopbackServer,
            GatewayLoopbackServerBindError,
        )

        GatewayLoopbackServer(
            bind="0.0.0.0",
            port=0,
            db_path=db_path,
            ready_file=None,
            loopback_token="token",
        )
    except GatewayLoopbackServerBindError as error:
        assert error.reason == "non_loopback_bind_blocked"
    else:
        raise AssertionError("expected GatewayLoopbackServerBindError")
