from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue


HardCloseDecision = Literal["report", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True, strict=True)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "password=",
    "token=",
    "private_key",
    "-----begin",
)
_REQUIRED_CHECKPOINTS: Final[tuple[tuple[str, str], ...]] = (
    ("W205", "zeus-w205-current-docs-sync.txt"),
    ("W206", "zeus-w206-rc-coverage-audit.txt"),
    ("W207", "zeus-w207-rc-smoke-eval.txt"),
    ("W208", "zeus-w208-rc-source-metrics.txt"),
    ("W209", "zeus-w209-rc-live-opt-in-boundary.txt"),
    ("W210", "zeus-w210-rc-security-boundary.txt"),
    ("W211", "zeus-w211-rc-release-boundary.txt"),
)
_RESIDUAL_BLOCKERS: Final[tuple[str, ...]] = (
    "production_live_surface_evidence_required",
    "project_mode_release_gate_required",
    "git_backed_publication_required",
)


class RcHardCloseResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: HardCloseDecision
    scope_closed_at_checkpoint: Literal["W212"]
    completed_checkpoint_ids: tuple[str, ...]
    completed_checkpoint_count: int
    missing_checkpoint_ids: tuple[str, ...]
    missing_checkpoint_artifacts: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    residual_blockers: tuple[str, ...]
    hard_close_ready: bool
    production_live_ready: bool = False
    release_publication_allowed: bool = False
    independent_review_required: bool = True
    final_security_review_required: bool = True
    raw_secret_marker_detected: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RcHardCloseResult:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})


def build_rc_hard_close(
    *,
    root: Optional[Path] = None,
    evidence_root: Optional[Path] = None,
    raw_review_note: Optional[str] = None,
) -> RcHardCloseResult:
    project_root = Path.cwd() if root is None else root
    evidence_dir = project_root / "evidence" if evidence_root is None else evidence_root
    completed, missing_ids, missing_artifacts = _checkpoint_status(evidence_dir)
    raw_secret_marker_detected = _has_secret_marker(raw_review_note or "")
    blocked_reasons = _blocked_reasons(missing_artifacts, raw_secret_marker_detected)
    hard_close_ready = not blocked_reasons
    result = RcHardCloseResult(
        decision="report" if hard_close_ready else "blocked",
        scope_closed_at_checkpoint="W212",
        completed_checkpoint_ids=completed,
        completed_checkpoint_count=len(completed),
        missing_checkpoint_ids=missing_ids,
        missing_checkpoint_artifacts=missing_artifacts,
        blocked_reasons=blocked_reasons,
        residual_blockers=_RESIDUAL_BLOCKERS,
        hard_close_ready=hard_close_ready,
        production_live_ready=False,
        release_publication_allowed=False,
        independent_review_required=True,
        final_security_review_required=True,
        raw_secret_marker_detected=raw_secret_marker_detected,
        credential_material_accessed=False,
        network_opened=False,
        handler_executed=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _checkpoint_status(evidence_dir: Path) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    completed = []
    missing_ids = []
    missing_artifacts = []
    for checkpoint_id, artifact_name in _REQUIRED_CHECKPOINTS:
        if (evidence_dir / artifact_name).is_file():
            completed.append(checkpoint_id)
        else:
            missing_ids.append(checkpoint_id)
            missing_artifacts.append(artifact_name)
    return tuple(completed), tuple(missing_ids), tuple(missing_artifacts)


def _blocked_reasons(missing_artifacts: tuple[str, ...], raw_secret_marker_detected: bool) -> tuple[str, ...]:
    reasons = []
    if missing_artifacts:
        reasons.append("missing_required_checkpoint_artifact")
    if raw_secret_marker_detected:
        reasons.append("raw_secret_marker_detected")
    return tuple(reasons)


def _has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
