from __future__ import annotations

import hashlib
from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.decision_api_runtime import ZeusDecisionEngine
from zeus_agent.mcp_gateway_runtime import scan_for_injection
from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

_KV_PREFIX: Final = "skill.q."


class SkillRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    name: str
    manifest_hash: str
    source: str
    status: str = "quarantined"  # quarantined | active
    injection_findings: tuple[str, ...] = ()


class SkillQuarantine:
    """Install → quarantine + hash-pin + injection scan; activation is review;
    drift re-quarantines. A skill is supply chain, not content."""

    def __init__(self, *, engine: ZeusDecisionEngine, store: SQLiteControlPlaneStore) -> None:
        self.engine = engine
        self.store = store

    def register_skill(self, *, name: str, manifest_text: str, source: str) -> SkillRecord:
        findings = scan_for_injection(manifest_text)
        record = SkillRecord(
            name=name.strip(),
            manifest_hash=_hash(manifest_text),
            source=source.strip(),
            status="quarantined",
            injection_findings=findings,
        )
        self._save(record)
        self.engine.recorder.record_decision(
            run_id="run.skill.quarantine",
            payload={
                "capability_id": "skill.install",
                "target": record.name,
                "decision": "notify",
                "reason": "quarantined_on_install",
                "manifest_hash": record.manifest_hash,
                "source": record.source,
                "injection_findings": list(findings),
            },
        )
        return record

    def activate(self, name: str, *, principal_id: str = "operator.local") -> dict[str, JsonValue]:
        record = self.get(name)
        if record is None:
            return {"activated": False, "reason": "unknown_skill"}
        if record.injection_findings:
            event = self.engine.recorder.record_decision(
                run_id="run.skill.quarantine",
                payload={
                    "capability_id": "skill.activate",
                    "target": name,
                    "decision": "deny",
                    "reason": "injection_findings_block_activation",
                    "principal_id": principal_id,
                },
            )
            return {
                "activated": False,
                "reason": "injection_findings_block_activation",
                "receipt_id": event.record_id,
            }
        self._save(record.model_copy(update={"status": "active"}))
        event = self.engine.recorder.record_decision(
            run_id="run.skill.quarantine",
            payload={
                "capability_id": "skill.activate",
                "target": name,
                "decision": "allow",
                "reason": "operator_review",
                "manifest_hash": record.manifest_hash,
                "principal_id": principal_id,
            },
        )
        return {"activated": True, "receipt_id": event.record_id}

    def reconcile(self, *, name: str, manifest_text: str) -> SkillRecord:
        """A changed manifest is a rug-pull: straight back to quarantine."""
        record = self.get(name)
        observed = _hash(manifest_text)
        if record is None:
            return self.register_skill(name=name, manifest_text=manifest_text, source="reconcile")
        if record.manifest_hash == observed:
            return record
        requarantined = record.model_copy(
            update={
                "manifest_hash": observed,
                "status": "quarantined",
                "injection_findings": scan_for_injection(manifest_text),
            }
        )
        self._save(requarantined)
        self.engine.recorder.record_decision(
            run_id="run.skill.quarantine",
            payload={
                "capability_id": "skill.install",
                "target": name,
                "decision": "notify",
                "reason": "requarantined_manifest_changed",
                "manifest_hash": observed,
            },
        )
        return requarantined

    def active_skills(self) -> tuple[str, ...]:
        names: list[str] = []
        for _name, raw in self._all():
            try:
                record = SkillRecord.model_validate_json(raw)
            except ValueError:
                continue
            if record.status == "active":
                names.append(record.name)
        return tuple(sorted(names))

    def get(self, name: str) -> Optional[SkillRecord]:
        raw = self.store.kv_get(_KV_PREFIX + name.strip())
        if raw is None:
            return None
        try:
            return SkillRecord.model_validate_json(raw)
        except ValueError:
            return None

    def _save(self, record: SkillRecord) -> None:
        self.store.kv_set(_KV_PREFIX + record.name, record.model_dump_json())
        self._index_add(record.name)

    def _all(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for name in self._known_names():
            raw = self.store.kv_get(_KV_PREFIX + name)
            if raw is not None:
                rows.append((name, raw))
        return rows

    def _known_names(self) -> tuple[str, ...]:
        raw = self.store.kv_get("skill.q-index")
        names = set((raw or "").split("\n")) - {""}
        return tuple(sorted(names))

    def _index_add(self, name: str) -> None:
        names = set(self._known_names()) | {name}
        self.store.kv_set("skill.q-index", "\n".join(sorted(names)))


def _hash(manifest_text: str) -> str:
    return hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
