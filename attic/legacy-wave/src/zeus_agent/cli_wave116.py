from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.cli_wave105 import _execution_result
from zeus_agent.live_remote_executor_preflight_runtime import LiveRemoteExecutorPreflightResult
from zeus_agent.live_remote_transport_policy_runtime import LiveRemoteTransportPolicyResult
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditResult
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownRuntime


def register_wave116_commands(app: typer.Typer) -> None:
    @app.command("live-transport-teardown-record")
    def live_transport_teardown_record(
        home: Path = typer.Option(..., "--home"),
        adapter_kind: str = typer.Option(..., "--adapter-kind"),
        policy_json: str = typer.Option(..., "--policy-json"),
        preflight_json: str = typer.Option(..., "--preflight-json"),
        execution_json: str = typer.Option(..., "--execution-json"),
        audit_json: str = typer.Option(..., "--audit-json"),
        teardown_ref: str = typer.Option(..., "--teardown-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            policy = LiveRemoteTransportPolicyResult.model_validate_json(policy_json)
            preflight = LiveRemoteExecutorPreflightResult.model_validate_json(preflight_json)
            execution = _execution_result(adapter_kind=adapter_kind, execution_json=execution_json)
            audit = LiveTransportAuditResult.model_validate_json(audit_json)
        except (json.JSONDecodeError, ValidationError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_transport_teardown",
                    "error": str(exc),
                    "ledger_recorded": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveTransportTeardownRuntime().record(
            home=home,
            adapter_kind=adapter_kind,
            policy=policy,
            preflight=preflight,
            execution=execution,
            audit=audit,
            teardown_ref=teardown_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
