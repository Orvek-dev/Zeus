from __future__ import annotations

import json
from json import JSONDecodeError

import typer
from pydantic import JsonValue, ValidationError

from zeus_agent.approval_receipt_runtime import ApprovalReceiptResult
from zeus_agent.cli_wave105 import _execution_result
from zeus_agent.live_operator_proof_runtime import LiveOperatorProofResult
from zeus_agent.live_production_approval_runtime import LiveProductionApprovalRuntime
from zeus_agent.live_transport_audit_runtime import LiveTransportAuditResult
from zeus_agent.live_transport_teardown_runtime import LiveTransportTeardownResult


def register_wave120_commands(app: typer.Typer) -> None:
    @app.command("live-production-approval")
    def live_production_approval(
        adapter_kind: str = typer.Option(..., "--adapter-kind"),
        execution_json: str = typer.Option(..., "--execution-json"),
        audit_json: str = typer.Option(..., "--audit-json"),
        teardown_json: str = typer.Option(..., "--teardown-json"),
        approval_receipt_json: str = typer.Option(..., "--approval-receipt-json"),
        operator_proof_json: str = typer.Option(..., "--operator-proof-json"),
        production_ref: str = typer.Option(..., "--production-ref"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        try:
            execution = _execution_result(adapter_kind=adapter_kind, execution_json=execution_json)
            if execution is None:
                raise ValueError("unsupported_adapter_kind")
            audit = LiveTransportAuditResult.model_validate_json(audit_json)
            teardown = LiveTransportTeardownResult.model_validate_json(teardown_json)
            receipt = ApprovalReceiptResult.model_validate_json(approval_receipt_json)
            proof = LiveOperatorProofResult.model_validate_json(operator_proof_json)
        except (JSONDecodeError, ValidationError, ValueError) as exc:
            _print_payload(
                {
                    "decision": "blocked",
                    "reason": "malformed_live_production_approval",
                    "error": str(exc),
                    "production_claim_authorized": False,
                    "live_production_claimed": False,
                },
                as_json=as_json,
            )
            return
        result = LiveProductionApprovalRuntime().approve(
            adapter_kind=adapter_kind,
            execution=execution,
            audit=audit,
            teardown=teardown,
            approval_receipt=receipt,
            operator_proof=proof,
            production_ref=production_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
