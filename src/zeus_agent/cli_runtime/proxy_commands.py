from __future__ import annotations

import json
from pathlib import Path

import typer

from .context import echo_json, is_loopback, state_for_home


def register_proxy_commands(app: typer.Typer) -> None:
    @app.command("proxy", help="Serve the governed LLM proxy.")
    def proxy(
        upstream: str = typer.Option(..., "--upstream", help="Upstream base, e.g. https://api.openai.com"),
        port: int = typer.Option(8788, "--port"),
        bind: str = typer.Option("127.0.0.1", "--bind", help="Listen address (local-first by default)."),
        require_v1_auth: bool = typer.Option(
            False, "--require-v1-auth", help="Require an x-zeus-v1-token on /v1 requests."
        ),
        unsafe_no_v1_auth: bool = typer.Option(
            False, "--unsafe-no-v1-auth", help="Allow a non-loopback bind with NO /v1 auth."
        ),
        hook_owned_host: list[str] = typer.Option(
            [],
            "--hook-owned-host",
            help="Host whose own blocking pre_tool_call hook owns ASK. Repeatable.",
        ),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.decision_api_runtime import HostKind
        from zeus_agent.pairing_runtime import PairingManager
        from zeus_agent.proxy_runtime import (
            LlmProxyEngine,
            run_proxy_server,
            seed_proxy_capability_store,
        )
        from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore
        from zeus_agent.zeusd_runtime import ZeusApiSurface

        try:
            owned = frozenset(HostKind(h.strip().lower().replace("-", "_")) for h in hook_owned_host)
        except ValueError as exc:
            raise typer.BadParameter("unknown --hook-owned-host: {0}".format(exc)) from exc
        if not is_loopback(bind) and not require_v1_auth and not unsafe_no_v1_auth:
            raise typer.BadParameter(
                "non-loopback --bind {0} exposes /v1 with no auth; pass --require-v1-auth "
                "(issue tokens with `zeus pair --issue-v1-token <host>`) or --unsafe-no-v1-auth "
                "to accept the risk".format(bind)
            )

        state = state_for_home(home)
        store = SQLiteControlPlaneStore(state.state_path)
        engine = state.build_engine(capabilities=seed_proxy_capability_store())
        proxy_engine = LlmProxyEngine(
            engine=engine,
            store=store,
            persist_taint=state.save_taint,
            hook_owned_hosts=owned,
        )
        pairing = PairingManager(store)
        api = ZeusApiSurface(engine=engine, pairing=pairing)
        typer.echo(
            json.dumps(
                {
                    "listening": "http://{0}:{1}".format(bind, port),
                    "surfaces": ["/v1 (llm proxy)", "/zeus (decide/record/brief, pairing-gated)"],
                    "upstream": upstream,
                    "v1_auth": "required"
                    if require_v1_auth
                    else "open (loopback)"
                    if is_loopback(bind)
                    else "OPEN (unsafe)",
                    "note": "model keys stay host-side; auth headers pass through",
                }
            ),
            err=True,
        )
        run_proxy_server(
            host=bind,
            port=port,
            engine=proxy_engine,
            upstream_base=upstream,
            api=api,
            v1_token_required=require_v1_auth,
            pairing=pairing,
        )

    @app.command("budget", help="Show budgets, or set a hard pre-call limit for a scope.")
    def budget(
        scope: str | None = typer.Option(None, "--scope", help="run | objective | fleet"),
        scope_id: str | None = typer.Option(None, "--id", help="run/objective id (fleet uses 'fleet')."),
        limit: int | None = typer.Option(None, "--limit", help="Max units (micro-USD) for the scope."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

        store = SQLiteControlPlaneStore(state_for_home(home).state_path)
        if limit is not None:
            if scope not in {"run", "objective", "fleet"}:
                raise typer.BadParameter("--scope must be run, objective, or fleet")
            resolved_id = scope_id if scope_id is not None else ("fleet" if scope == "fleet" else None)
            if resolved_id is None:
                raise typer.BadParameter("--id is required for run/objective scopes")
            store.set_budget_limit(scope, resolved_id, max(limit, 0))
        echo_json(
            [
                {"scope": row[0], "id": row[1], "limit_units": row[2], "spent_units": row[3]}
                for row in store.budget_rows()
            ]
        )
