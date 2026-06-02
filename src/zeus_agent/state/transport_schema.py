from __future__ import annotations

TRANSPORT_RUNTIME_SCHEMA = [
    "CREATE TABLE IF NOT EXISTS runtime_state_transport_manifests("
    "manifest_id TEXT PRIMARY KEY, transport_id TEXT NOT NULL, kind TEXT NOT NULL, "
    "capability_id TEXT NOT NULL, payload_json TEXT NOT NULL, "
    "evidence_id TEXT NOT NULL REFERENCES evidence_state_records(evidence_id), "
    "idempotency_key TEXT NOT NULL UNIQUE, live_transport INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS runtime_state_transport_probe_receipts("
    "probe_receipt_id TEXT PRIMARY KEY, probe_id TEXT NOT NULL, transport_id TEXT NOT NULL, "
    "health TEXT NOT NULL, payload_json TEXT NOT NULL, "
    "evidence_id TEXT NOT NULL REFERENCES evidence_state_records(evidence_id), "
    "idempotency_key TEXT NOT NULL UNIQUE, handler_executed INTEGER NOT NULL, "
    "network_opened INTEGER NOT NULL, side_effects INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS runtime_state_transport_health("
    "transport_id TEXT PRIMARY KEY, health TEXT NOT NULL, "
    "evidence_id TEXT NOT NULL REFERENCES evidence_state_records(evidence_id), "
    "idempotency_key TEXT NOT NULL UNIQUE)",
    "CREATE TABLE IF NOT EXISTS runtime_state_transport_policy_blocks("
    "policy_block_id TEXT PRIMARY KEY, reason TEXT NOT NULL, transport_id TEXT, "
    "payload_json TEXT NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence_state_records(evidence_id), "
    "idempotency_key TEXT NOT NULL UNIQUE, handler_executed INTEGER NOT NULL, "
    "network_opened INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS runtime_state_transport_evidence_links("
    "record_kind TEXT NOT NULL, record_id TEXT NOT NULL, "
    "evidence_id TEXT NOT NULL REFERENCES evidence_state_records(evidence_id), "
    "PRIMARY KEY(record_kind, record_id, evidence_id))",
]
