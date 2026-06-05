from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.entry_runtime import default_zeus_home
from zeus_agent.gateway_cockpit_runtime import GatewayCockpitRuntime
from zeus_agent.gateway_pairing_runtime import GatewayPairingRuntime
from zeus_agent.gateway_settings_runtime import GatewaySettingsRuntime


def register_wave45_commands(app: typer.Typer) -> None:
    @app.command("gateway")
    def gateway(
        adapter_id: Optional[str] = typer.Option(None, "--adapter-id"),
        add_adapter: Optional[str] = typer.Option(None, "--add", help="Add a gateway target to local quarantined config."),
        pair_adapter: Optional[str] = typer.Option(None, "--pair", help="Record a reference-only gateway pairing proof."),
        target: Optional[str] = typer.Option(None, "--target", help="Gateway delivery target to allowlist locally."),
        pairing_proof_ref: Optional[str] = typer.Option(None, "--pairing-proof-ref", help="Reference to local pairing proof evidence."),
        list_config: bool = typer.Option(False, "--list-config", help="List local gateway target config."),
        list_pairings: bool = typer.Option(False, "--list-pairings", help="List local gateway pairing proofs."),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        zeus_home = home or default_zeus_home()
        runtime = GatewaySettingsRuntime(zeus_home)
        if add_adapter is not None:
            _print_payload(runtime.add(adapter_ref=add_adapter, target=target or "").to_payload(), as_json=as_json)
            return
        if pair_adapter is not None:
            _print_payload(
                GatewayPairingRuntime(zeus_home).pair(
                    adapter_id=pair_adapter,
                    target=target or "",
                    proof_ref=pairing_proof_ref or "",
                ).to_payload(),
                as_json=as_json,
            )
            return
        if list_config:
            _print_payload(runtime.list().to_payload(), as_json=as_json)
            return
        if list_pairings:
            _print_payload(GatewayPairingRuntime(zeus_home).list().to_payload(), as_json=as_json)
            return
        result = GatewayCockpitRuntime().build(adapter_id=adapter_id)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
