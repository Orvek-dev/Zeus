"""Skill lifecycle management."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import re

from zeus_agent.paths import PRIVATE_FILE_MODE, ensure_private_dir, skills_dir
from zeus_agent.schemas.skill import SkillEvaluation, SkillManifest
from zeus_agent.schemas.trace_event import new_trace_event
from zeus_agent.security.redaction import redact_text
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.jsonio import read_json, write_private_json

REQUIRED_SECTIONS = ("## Purpose", "## Triggers", "## Procedure", "## Verification")


class SkillLifecycleError(RuntimeError):
    """Raised when a skill transition is invalid."""


def draft_skill(
    name: str,
    description: str,
    *,
    triggers: list[str] | None = None,
    procedure: str = "",
    home: Path | None = None,
) -> SkillManifest:
    cleaned_description = redact_text(description)
    cleaned_procedure = redact_text(procedure or "Follow the approved GoalContract, collect evidence, and stop on policy conflicts.")
    cleaned_triggers = [redact_text(trigger).value for trigger in (triggers or [])]
    skill_id = _skill_id(name)
    skill_root = _skill_dir(skill_id, home)
    ensure_private_dir(skill_root)
    procedure_path = skill_root / "SKILL.md"
    procedure_path.write_text(
        _skill_markdown(
            name,
            cleaned_description.value,
            cleaned_triggers,
            cleaned_procedure.value,
        ),
        encoding="utf-8",
    )
    os.chmod(procedure_path, PRIVATE_FILE_MODE)
    manifest = SkillManifest(
        skill_id=skill_id,
        name=name,
        description=cleaned_description.value,
        triggers=cleaned_triggers,
        procedure_path=str(procedure_path),
    )
    _save_manifest(manifest, home)
    EventLog(home).append(
        new_trace_event(
            "skill.drafted",
            payload={"skill_id": skill_id, "name": name},
        )
    )
    return manifest


def test_skill(skill_id: str, *, home: Path | None = None) -> SkillManifest:
    manifest = load_skill(skill_id, home=home)
    procedure_text = Path(manifest.procedure_path).read_text(encoding="utf-8")
    findings: list[str] = []
    for section in REQUIRED_SECTIONS:
        if section not in procedure_text:
            findings.append(f"missing section: {section}")
    if len(procedure_text.strip()) < 160:
        findings.append("procedure is too short to be reusable")
    if not manifest.triggers:
        findings.append("no triggers defined")
    redaction = redact_text(procedure_text)
    if redaction.redacted:
        findings.append("procedure contained redacted sensitive text")
    score = max(0.0, 1.0 - (len(findings) * 0.25))
    manifest.state = "testing"
    manifest.updated_at = datetime.now(UTC)
    manifest.evaluation = SkillEvaluation(
        passed=not findings,
        score=score,
        findings=findings,
    )
    _save_manifest(manifest, home)
    EventLog(home).append(
        new_trace_event(
            "skill.tested",
            payload={"skill_id": skill_id, "passed": manifest.evaluation.passed, "score": score},
        )
    )
    return manifest


test_skill.__test__ = False


def promote_skill(skill_id: str, *, home: Path | None = None) -> SkillManifest:
    manifest = load_skill(skill_id, home=home)
    if manifest.evaluation is None or not manifest.evaluation.passed:
        raise SkillLifecycleError("skill must pass evaluation before promotion")
    manifest.state = "promoted"
    manifest.updated_at = datetime.now(UTC)
    _save_manifest(manifest, home)
    EventLog(home).append(new_trace_event("skill.promoted", payload={"skill_id": skill_id}))
    return manifest


def retire_skill(skill_id: str, *, home: Path | None = None) -> SkillManifest:
    manifest = load_skill(skill_id, home=home)
    manifest.state = "retired"
    manifest.updated_at = datetime.now(UTC)
    _save_manifest(manifest, home)
    EventLog(home).append(new_trace_event("skill.retired", payload={"skill_id": skill_id}))
    return manifest


def list_skills(*, home: Path | None = None) -> list[dict[str, str]]:
    root = skills_dir(home)
    if not root.exists():
        return []
    items: list[dict[str, str]] = []
    for manifest_path in sorted(root.glob("*/manifest.json")):
        manifest = SkillManifest.model_validate(read_json(manifest_path))
        items.append(
            {
                "skill_id": manifest.skill_id,
                "name": manifest.name,
                "state": manifest.state,
                "score": "" if manifest.evaluation is None else str(manifest.evaluation.score),
            }
        )
    return items


def load_skill(skill_id: str, *, home: Path | None = None) -> SkillManifest:
    return SkillManifest.model_validate(read_json(_manifest_path(skill_id, home)))


def _skill_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        slug = "skill"
    digest = hashlib.sha256(name.encode()).hexdigest()[:8]
    return f"skill_{slug}_{digest}"


def _skill_dir(skill_id: str, home: Path | None) -> Path:
    if not re.fullmatch(r"skill_[a-z0-9-]+_[a-f0-9]{8}", skill_id):
        raise SkillLifecycleError(f"invalid skill id: {skill_id}")
    return skills_dir(home) / skill_id


def _manifest_path(skill_id: str, home: Path | None) -> Path:
    return _skill_dir(skill_id, home) / "manifest.json"


def _save_manifest(manifest: SkillManifest, home: Path | None) -> Path:
    return write_private_json(_manifest_path(manifest.skill_id, home), manifest.model_dump(mode="json"))


def _skill_markdown(name: str, description: str, triggers: list[str], procedure: str) -> str:
    trigger_lines = "\n".join(f"- {trigger}" for trigger in triggers) or "- Manual operator selection"
    return "\n".join(
        [
            f"# {name}",
            "",
            "## Purpose",
            description,
            "",
            "## Triggers",
            trigger_lines,
            "",
            "## Procedure",
            procedure,
            "",
            "## Verification",
            "- The skill has a concrete trigger.",
            "- The skill produces observable evidence.",
            "- The skill stops when policy, budget, or approval gates block progress.",
            "",
        ]
    )
