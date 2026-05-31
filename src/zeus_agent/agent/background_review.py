"""Deterministic background review for memory and skill candidates.

Hermes runs a post-turn review to capture durable knowledge. Zeus keeps the
same lifecycle idea, but starts conservatively: the reviewer writes evidence and
skill candidates only when the run produced a reusable, safety-relevant pattern.
"""

from __future__ import annotations

from pathlib import Path

from zeus_agent.core.mneme import list_evidence, record_evidence
from zeus_agent.core.skills import draft_skill
from zeus_agent.schemas.skill import SkillManifest


def review_run_for_skill_updates(run_id: str, *, home: Path | None = None) -> SkillManifest | None:
    records = list_evidence(run_id, home=home)
    if not records:
        return None
    command_failures = [
        item for item in records if item.get("evidence_type") == "command" and item.get("passed") is False
    ]
    blocked_verifications = [
        item for item in records if item.get("evidence_type") == "verification" and item.get("passed") is False
    ]
    if len(command_failures) + len(blocked_verifications) < 2:
        record_evidence(
            run_id,
            "skill",
            "Background review completed; no durable skill candidate promoted.",
            passed=True,
            payload={"evidence_count": len(records)},
            home=home,
        )
        return None

    manifest = draft_skill(
        f"run-{run_id[-8:]}-recovery-pattern",
        "Reusable recovery pattern proposed from repeated blocked or failed evidence.",
        triggers=["repeated command failure", "blocked verification", "sisyphus escalation"],
        procedure=(
            "Read the GoalContract and Mneme evidence first. Identify the repeated failure. "
            "Prefer read-only inspection and checkpointed repairs. Escalate when the next "
            "step needs credentials, network writes, destructive commands, or unverifiable assumptions."
        ),
        home=home,
    )
    record_evidence(
        run_id,
        "skill",
        f"Drafted skill candidate {manifest.skill_id} from repeated blocked evidence.",
        passed=True,
        payload={"skill_id": manifest.skill_id, "evidence_count": len(records)},
        home=home,
    )
    return manifest

