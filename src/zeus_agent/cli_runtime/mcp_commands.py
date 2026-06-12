from __future__ import annotations

import json
from pathlib import Path

import typer

from .context import echo_json, state_for_home


def register_mcp_commands(app: typer.Typer) -> None:
    @app.command("gateway", help="Serve the MCP gateway over stdio.")
    def gateway_serve(
        home: Path | None = typer.Option(None, "--home"),
        session_id: str = typer.Option("mcp-gateway.default", "--session-id"),
        principal: str = typer.Option("agent.mcp_client", "--principal"),
    ) -> None:
        from zeus_agent.mcp_gateway_runtime import GatewaySession, serve_stdio

        _state_obj, gateway = _gateway_parts(home)
        gateway.sync_tools()
        serve_stdio(gateway, GatewaySession(principal_id=principal, session_id=session_id))

    @app.command("mcp", help="Inspect and review gateway-imported MCP tools.")
    def mcp(
        sync: bool = typer.Option(False, "--sync", help="Import/reconcile downstream tools."),
        approve: str | None = typer.Option(None, "--approve", help="De-quarantine a tool after review."),
        side_effect: str | None = typer.Option(None, "--side-effect", help="none|local_write|account_write|public_write."),
        reversibility: str | None = typer.Option(None, "--reversibility", help="reversible|compensable|irreversible."),
        tool_budget: str | None = typer.Option(None, "--tool-budget", help="capability_id=N max calls."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.capability_registry_runtime import CapabilityRecord, SideEffectClass
        from zeus_agent.trust_loop_runtime import Reversibility, SQLiteControlPlaneStore

        state, gateway = _gateway_parts(home)
        if sync:
            echo_json(gateway.sync_tools().model_dump(mode="json"))
            return
        if approve is not None:
            try:
                parsed_side_effect = SideEffectClass(side_effect) if side_effect else None
                parsed_reversibility = Reversibility(reversibility) if reversibility else None
            except ValueError as exc:
                raise typer.BadParameter(str(exc))
            approved = gateway.approve_tool(
                approve, side_effect=parsed_side_effect, reversibility=parsed_reversibility
            )
            echo_json({"approved": approved, "capability_id": approve})
            return
        if tool_budget is not None:
            capability_id, _, raw_limit = tool_budget.partition("=")
            if not capability_id or not raw_limit.isdigit():
                raise typer.BadParameter("--tool-budget expects capability_id=N")
            SQLiteControlPlaneStore(state.state_path).set_budget_limit(
                "capability", capability_id, int(raw_limit)
            )
            echo_json({"capability_id": capability_id, "max_calls": int(raw_limit)})
            return
        store = SQLiteControlPlaneStore(state.state_path)
        rows = []
        for capability_id, raw in store.capability_all():
            try:
                record = CapabilityRecord.model_validate_json(raw)
            except ValueError:
                continue
            if record.server_ref is None and not capability_id.startswith("mcp."):
                continue
            rows.append(
                {
                    "capability_id": capability_id,
                    "status": record.status.value,
                    "schema_hash": (record.schema_hash or "")[:12],
                    "server": record.server_ref,
                }
            )
        if not rows:
            echo_json(
                {
                    "tools": [],
                    "note": "no downstream MCP tools imported yet - this is expected until a "
                    "downstream server is added. Run `zeus mcp --sync` after configuring a "
                    "downstream MCP server; imported tools arrive quarantined for review.",
                }
            )
            return
        echo_json(rows)


def _gateway_parts(home: Path | None):
    from zeus_agent.mcp_gateway_runtime import McpGateway, StdioMcpClient
    from zeus_agent.proxy_runtime import seed_proxy_capability_store
    from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

    state = state_for_home(home)
    servers_path = state.root / "mcp-servers.json"
    clients = []
    if servers_path.exists():
        try:
            config = json.loads(servers_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            config = {}
        for name, spec in (config.get("servers") or {}).items():
            command = spec.get("command") if isinstance(spec, dict) else None
            if isinstance(command, list) and command:
                clients.append(StdioMcpClient(str(name), [str(part) for part in command]))
    gateway = McpGateway(
        engine=state.build_engine(capabilities=seed_proxy_capability_store()),
        store=SQLiteControlPlaneStore(state.state_path),
        downstreams=tuple(client.downstream() for client in clients),
        persist_taint=state.save_taint,
    )
    return state, gateway
