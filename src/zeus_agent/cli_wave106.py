from __future__ import annotations

import json
from json import JSONDecodeError

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.live_response_redaction_runtime import LiveResponseRedactionRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditResult


def register_wave106_commands(app: typer.Typer) -> None:
    @app.command("live-response-redact")
    def live_response_redact(
        audit_json: str = typer.Option(..., "--audit-json"),
        response_json: str = typer.Option(..., "--response-json"),
        response_ref: str = typer.Option(..., "--response-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            audit = LiveTransportAuditResult.model_validate_json(audit_json)
            response_payload = _response_payload(response_json)
        except (JSONDecodeError, TypeError, ValidationError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_response_redaction",
                    "error": str(exc),
                    "network_opened": False,
                    "live_transport_enabled": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveResponseRedactionRuntime().redact(
            audit=audit,
            response_payload=response_payload,
            response_ref=response_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _response_payload(response_json: str) -> dict[str, JsonValue]:
    payload = json.loads(response_json)
    if not isinstance(payload, dict):
        raise TypeError("response_json_must_be_object")
    return payload


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
