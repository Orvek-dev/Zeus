from __future__ import annotations

RUNTIME_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS runtime_state_provider_executions("
    "provider_execution_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, "
    "goal_contract_id TEXT NOT NULL, provider TEXT NOT NULL, provider_id TEXT NOT NULL, "
    "model_id TEXT NOT NULL, envelope_json TEXT NOT NULL, broker_decision TEXT NOT NULL, "
    "evidence_id TEXT NOT NULL REFERENCES evidence_state_records(evidence_id), "
    "idempotency_key TEXT NOT NULL UNIQUE, live_transport INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS runtime_state_connector_executions("
    "connector_execution_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, "
    "goal_contract_id TEXT NOT NULL, connector_id TEXT NOT NULL, connector_kind TEXT NOT NULL, "
    "capability_id TEXT NOT NULL, envelope_json TEXT NOT NULL, broker_decision TEXT NOT NULL, "
    "handler_executed INTEGER NOT NULL, "
    "evidence_id TEXT NOT NULL REFERENCES evidence_state_records(evidence_id), "
    "idempotency_key TEXT NOT NULL UNIQUE, live_transport INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS runtime_state_execution_evidence_links("
    "execution_kind TEXT NOT NULL, execution_id TEXT NOT NULL, "
    "evidence_id TEXT NOT NULL REFERENCES evidence_state_records(evidence_id), "
    "PRIMARY KEY(execution_kind, execution_id, evidence_id))",
    "CREATE TABLE IF NOT EXISTS runtime_state_transport_promotions("
    "promotion_id TEXT PRIMARY KEY, capability_id TEXT NOT NULL, transport_kind TEXT NOT NULL, "
    "decision TEXT NOT NULL, reason TEXT NOT NULL, approval_required INTEGER NOT NULL, "
    "handler_executed INTEGER NOT NULL, network_opened INTEGER NOT NULL, "
    "retry_policy_json TEXT NOT NULL, rollback_plan_json TEXT NOT NULL, "
    "idempotency_key TEXT NOT NULL UNIQUE)",
]
