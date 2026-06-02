from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from zeus_agent.gateway_runtime.local_gateway import (
    GatewayDraftRequest,
    create_gateway_draft,
    record_api_draft_execution,
)
from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.skill_evolution.proposed_queue import (
    ProposedSkillQueue,
    queue_raw_secret_present,
)
from zeus_agent.state.memory_session_fts import (
    MemorySessionDocument,
    MemorySessionFTSIndex,
    raw_secret_present,
)
from zeus_agent.workflow_runtime.schedules import (
    SchedulePlanLedger,
    ScheduledObjectiveRequest,
)

Wave13Payload = dict[str, object]

_NOW = datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)
_EXPIRES = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)


def wave13_production_payload(home: Path) -> Wave13Payload:
    home.mkdir(parents=True, exist_ok=True)
    lease = _wave13_lease()
    gateway = create_gateway_draft(
        request=_gateway_request(),
        lease=lease,
        now=_NOW,
    )
    api = record_api_draft_execution(
        request=_api_request(),
        lease=lease,
        now=_NOW,
    )
    schedule = SchedulePlanLedger().plan(
        request=_schedule_request(),
        lease=lease,
        now=_NOW,
    )
    memory_index = MemorySessionFTSIndex()
    memory_record = memory_index.add(
        MemorySessionDocument(
            session_id="wave13.session.local",
            principal_id="wave13.principal.worker",
            raw_text="Gateway draft and cron plan were recorded for Wave13.",
            tags=("wave13", "production"),
        ),
    )
    skill_record = ProposedSkillQueue().queue_candidate(
        evidence_summary="Wave13 repeated production scaffold review",
        source_evidence_id="wave13.production.local",
        improvement_rationale="Keep gateway, cron, memory, and skills proposed-only.",
    )
    records = (
        gateway.record,
        api.record,
        schedule.record,
        memory_record,
        skill_record.candidate,
    )
    serialized = json.dumps([asdict(record) if hasattr(record, "__dataclass_fields__") else str(record) for record in records])
    return {
        "scenario_id": "C001",
        "home": str(home),
        "gateway_draft_created": gateway.decision == "drafted",
        "api_draft_execution_recorded": api.decision == "recorded",
        "cron_job_planned": schedule.decision == "planned" and schedule.record is not None,
        "scheduled_objective_job_created": schedule.record is not None,
        "memory_session_fts_recorded": bool(memory_index.search("wave13")),
        "skill_candidate_queued": skill_record.queued,
        "skill_promoted": skill_record.promoted,
        "regression_surface_created": "wave13" in serialized,
        "live_transport_allowed": lease.live_transport_allowed,
        "handler_executed": gateway.handler_executed or api.handler_executed or schedule.handler_executed,
        "network_opened": gateway.network_opened or api.network_opened or schedule.network_opened,
    }


def wave13_blocks_payload(home: Path, raw_secret: str) -> Wave13Payload:
    home.mkdir(parents=True, exist_ok=True)
    lease = _wave13_lease()
    gateway_missing = create_gateway_draft(
        request=_gateway_request(live_network=True),
        lease=None,
        now=_NOW,
    )
    cron_missing = SchedulePlanLedger().plan(
        request=_schedule_request(),
        lease=None,
        now=_NOW,
    )
    ledger = SchedulePlanLedger()
    first_schedule = ledger.plan(request=_schedule_request(), lease=lease, now=_NOW)
    duplicate_schedule = ledger.plan(request=_schedule_request(), lease=lease, now=_NOW)
    conflict_schedule = ledger.plan(
        request=_schedule_request(cron_expression="0 9 * * *"),
        lease=lease,
        now=_NOW,
    )
    memory_index = MemorySessionFTSIndex()
    memory_index.add(
        MemorySessionDocument(
            session_id="wave13.session.block",
            principal_id="wave13.principal.worker",
            raw_text="session captured {0}".format(raw_secret),
            tags=("wave13", "secret"),
        ),
    )
    queue = ProposedSkillQueue()
    auto_review = queue.review_auto_promotion_request(raw_secret)
    live_transport = create_gateway_draft(
        request=_gateway_request(live_network=True, network_host="gateway.local"),
        lease=lease,
        now=_NOW,
    )
    serialized = json.dumps(
        {
            "gateway_missing": gateway_missing.reason,
            "cron_missing": cron_missing.reason,
            "first_schedule": first_schedule.reason,
            "duplicate_schedule": duplicate_schedule.reason,
            "conflict_schedule": conflict_schedule.reason,
            "memory": [asdict(record) for record in memory_index.records()],
            "auto_review": auto_review.model_dump(mode="json"),
            "live_transport": live_transport.reason,
            "queue": [record.candidate.candidate_id for record in queue.records()],
        },
        sort_keys=True,
    )
    raw_secret_found = (
        raw_secret in serialized
        or raw_secret_present(memory_index.records(), raw_secret)
        or queue_raw_secret_present(queue.records(), raw_secret)
    )
    return {
        "scenario_id": "C002",
        "home": str(home),
        "gateway_without_lease": gateway_missing.decision,
        "cron_without_lease": cron_missing.decision,
        "duplicate_schedule_idempotent": duplicate_schedule.decision == "idempotent_replay",
        "conflicting_schedule_replay": conflict_schedule.decision,
        "memory_raw_secret_redacted": not raw_secret_present(memory_index.records(), raw_secret),
        "skill_auto_promotion": auto_review.status,
        "live_transport_enablement": live_transport.decision,
        "unleased_live_transport_opened": gateway_missing.network_opened,
        "raw_secret_present": raw_secret_found,
    }


def _wave13_lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="wave13.lease.fixture",
        objective_id="wave13.objective.production",
        principal_id="wave13.principal.worker",
        run_id="wave13.run.fixture",
        allowed_capabilities=(
            "gateway.local.draft",
            "api.tool.invoke",
            "cron.schedule.tick",
            "plugin.local.skill_review",
        ),
        credential_scopes=("external.gateway.readonly",),
        network_hosts=("gateway.local",),
        budget_limit=100,
        evidence_target="mneme.wave13.production",
        live_transport_allowed=False,
        issued_at=_NOW,
        expires_at=_EXPIRES,
    )


def _gateway_request(
    *,
    live_network: bool = False,
    network_host: str | None = None,
) -> GatewayDraftRequest:
    return GatewayDraftRequest(
        request_id="wave13.gateway.draft",
        capability_id="gateway.local.draft",
        route="/local/wave13",
        method="POST",
        body='{"draft": true}',
        live_network=live_network,
        network_host=network_host,
    )


def _api_request() -> GatewayDraftRequest:
    return GatewayDraftRequest(
        request_id="wave13.api.draft",
        capability_id="api.tool.invoke",
        route="/local/api/wave13",
        method="POST",
        body='{"execute": "draft-record-only"}',
    )


def _schedule_request(
    *,
    cron_expression: str = "0 * * * *",
) -> ScheduledObjectiveRequest:
    return ScheduledObjectiveRequest(
        schedule_id="wave13.schedule.objective",
        objective_id="wave13.objective.production",
        cron_expression=cron_expression,
        idempotency_key="wave13.schedule.key",
    )
