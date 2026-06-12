from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer

from .context import echo_json, state_for_home


def register_policy_commands(app: typer.Typer) -> None:
    @app.command("policy", help="Policy packs and NL rules; every change is governed and ledgered.")
    def policy(
        apply_pack_name: str | None = typer.Option(None, "--apply", help="Apply a policy pack by name."),
        confirm: bool = typer.Option(False, "--confirm", help="Operator confirmation for --apply/--rule."),
        rule: str | None = typer.Option(None, "--rule", help='NL rule, e.g. "weekly budget $12".'),
        hygiene_mode: str | None = typer.Option(
            None, "--hygiene-mode", help="Proxy log-hygiene mode: count|redact|block|ask."
        ),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.nl_policy_runtime import apply_rule_diff, parse_nl_rule, supported_grammar
        from zeus_agent.policy_pack_runtime import BUILTIN_PACKS, apply_pack, pack_by_name
        from zeus_agent.proxy_runtime import KV_HYGIENE_MODE, HygieneMode, hygiene_mode_of
        from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

        state = state_for_home(home)
        store = SQLiteControlPlaneStore(state.state_path)
        if apply_pack_name is not None:
            pack = pack_by_name(apply_pack_name)
            if pack is None:
                raise typer.BadParameter("unknown pack: {0}".format(apply_pack_name))
            echo_json(apply_pack(pack, engine=state.build_engine(), store=store, confirmed=confirm))
            return
        if rule is not None:
            diff = parse_nl_rule(rule)
            if diff is None:
                echo_json({"parsed": False, "supported": list(supported_grammar())})
                raise typer.Exit(code=1)
            if not confirm:
                echo_json({"parsed": True, "preview": diff.preview, "next": "rerun with --confirm"})
                return
            echo_json(apply_rule_diff(diff, store))
            return
        if hygiene_mode is not None:
            try:
                mode = HygieneMode(hygiene_mode.strip().lower())
            except ValueError as exc:
                raise typer.BadParameter("hygiene mode must be one of: count, redact, block, ask") from exc
            engine = state.build_engine()
            event = engine.recorder.record_decision(
                run_id="run.policy.hygiene",
                payload={
                    "capability_id": "policy.change",
                    "decision": "allow" if confirm else "ask",
                    "reason": "hygiene_mode_set:{0}".format(mode.value),
                    "principal_id": "operator.local",
                },
            )
            if not confirm:
                echo_json(
                    {
                        "parsed": True,
                        "preview": "set proxy hygiene mode -> {0}".format(mode.value),
                        "next": "rerun with --confirm",
                        "receipt_id": event.record_id,
                    }
                )
                return
            store.kv_set(KV_HYGIENE_MODE, mode.value)
            echo_json({"applied": True, "hygiene_mode": mode.value, "receipt_id": event.record_id})
            return
        echo_json(
            {
                "active_pack": store.kv_get("policy.active_pack"),
                "quiet_hours": store.kv_get("policy.quiet_hours"),
                "hygiene_mode": hygiene_mode_of(store).value,
                "packs": [
                    {"name": pack.name, "description": pack.description} for pack in BUILTIN_PACKS
                ],
            }
        )

    @app.command("digest", help="Weekly governance digest where NOTIFY-tier actions land.")
    def digest(
        ack: bool = typer.Option(False, "--ack", help="Acknowledge this week's digest."),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.digest_runtime import ack_digest, build_digest
        from zeus_agent.trust_loop_runtime import (
            FlightRecorder,
            SQLiteControlPlaneStore,
            SQLiteEvidenceLedger,
            SQLiteTrustStatStore,
        )

        state = state_for_home(home)
        store = SQLiteControlPlaneStore(state.state_path)
        now = datetime.now(timezone.utc)
        if ack:
            echo_json(ack_digest(store, now=now))
            return
        recorder = FlightRecorder(SQLiteEvidenceLedger(state.ledger_path))
        echo_json(build_digest(recorder, store, SQLiteTrustStatStore(state.trust_path), now=now))

    @app.command("pair", help="Approve host pairings; the one-tap trust step that is never skipped.")
    def pair(
        approve_code: str | None = typer.Option(None, "--approve", help="Approve a host's pairing code."),
        revoke_code: str | None = typer.Option(None, "--revoke", help="Revoke a pairing."),
        request_host: str | None = typer.Option(None, "--request", help="Request a pairing for a host name."),
        issue_v1_token: str | None = typer.Option(
            None, "--issue-v1-token", help="Issue a static /v1 proxy token for a host name."
        ),
        token_ttl_days: int = typer.Option(
            30, "--token-ttl-days", help="Expiry for --issue-v1-token (0 = never expires)."
        ),
        revoke_v1_token: str | None = typer.Option(
            None, "--revoke-v1-token", help="Revoke a previously issued /v1 token."
        ),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.pairing_runtime import PairingManager
        from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

        manager = PairingManager(SQLiteControlPlaneStore(state_for_home(home).state_path))
        if request_host is not None:
            echo_json(manager.request(request_host))
            return
        if issue_v1_token is not None:
            echo_json(manager.issue_v1_token(issue_v1_token, ttl_days=token_ttl_days))
            return
        if revoke_v1_token is not None:
            echo_json({"revoked": manager.revoke_v1_token(revoke_v1_token)})
            return
        if approve_code is not None:
            echo_json({"approved": manager.approve(approve_code), "code": approve_code})
            return
        if revoke_code is not None:
            echo_json({"revoked": manager.revoke(revoke_code), "code": revoke_code})
            return
        raise typer.BadParameter(
            "use --approve CODE, --revoke CODE, --request HOST, --issue-v1-token HOST, "
            "or --revoke-v1-token TOKEN"
        )

    @app.command("brief", help="Session-recovery briefing: scoped, masked, ledgered, tainted-untrusted.")
    def brief(
        session_id: str = typer.Option(..., "--session-id", help="Host session to brief."),
        principal: str = typer.Option("agent.unknown", "--principal"),
        home: Path | None = typer.Option(None, "--home"),
    ) -> None:
        from zeus_agent.trust_loop_runtime import (
            FlightRecorder,
            GovernedLedgerReader,
            LedgerPrincipalKind,
            SQLiteEvidenceLedger,
        )

        state = state_for_home(home)
        reader = GovernedLedgerReader(FlightRecorder(SQLiteEvidenceLedger(state.ledger_path)))
        result = reader.read(
            principal_kind=LedgerPrincipalKind.agent,
            principal_id=principal,
            session_id=session_id,
        )
        echo_json(result.model_dump(mode="json"))
