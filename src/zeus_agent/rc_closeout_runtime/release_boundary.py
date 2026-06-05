from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue


ReleaseDecision = Literal["report", "blocked"]
ReleaseIntent = Literal["candidate", "publish"]

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


class RcReleaseBoundaryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: ReleaseDecision
    release_intent: ReleaseIntent
    version: str
    version_source: str
    package_artifacts: tuple[str, ...]
    package_artifact_count: int
    local_package_candidate_present: bool
    release_blockers: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    release_candidate_ready: bool
    release_publication_allowed: bool
    tag_allowed: bool
    push_allowed: bool
    github_release_allowed: bool
    raw_secret_marker_detected: bool
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RcReleaseBoundaryResult:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})


def build_rc_release_boundary(
    *,
    root: Optional[Path] = None,
    release_intent: ReleaseIntent = "candidate",
    raw_release_note: Optional[str] = None,
) -> RcReleaseBoundaryResult:
    project_root = Path.cwd() if root is None else root
    version = _read_pyproject_version(project_root / "pyproject.toml")
    artifacts = _package_artifacts(project_root / "dist", version)
    raw_secret_marker_detected = _has_secret_marker(raw_release_note or "")
    release_blockers = _release_blockers(project_root)
    blocked_reasons = _blocked_reasons(release_intent, raw_secret_marker_detected, release_blockers)
    result = RcReleaseBoundaryResult(
        decision="blocked" if blocked_reasons else "report",
        release_intent=release_intent,
        version=version,
        version_source="pyproject.toml",
        package_artifacts=artifacts,
        package_artifact_count=len(artifacts),
        local_package_candidate_present=len(artifacts) >= 2,
        release_blockers=release_blockers,
        blocked_reasons=blocked_reasons,
        release_candidate_ready=False,
        release_publication_allowed=False,
        tag_allowed=False,
        push_allowed=False,
        github_release_allowed=False,
        raw_secret_marker_detected=raw_secret_marker_detected,
        credential_material_accessed=False,
        network_opened=False,
        handler_executed=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _read_pyproject_version(path: Path) -> str:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    return match.group(1) if match else "unknown"


def _package_artifacts(dist_root: Path, version: str) -> tuple[str, ...]:
    if not dist_root.is_dir() or version == "unknown":
        return ()
    prefix = f"zeus_agent-{version}"
    return tuple(sorted(path.name for path in dist_root.iterdir() if path.is_file() and path.name.startswith(prefix)))


def _release_blockers(root: Path) -> tuple[str, ...]:
    blockers = ["project_mode_release_gate_required", "production_live_surface_evidence_required"]
    if not (root / ".git").is_dir():
        blockers.append("non_git_cwd_release_blocked")
    return tuple(blockers)


def _blocked_reasons(
    release_intent: ReleaseIntent,
    raw_secret_marker_detected: bool,
    release_blockers: tuple[str, ...],
) -> tuple[str, ...]:
    reasons = []
    if release_intent == "publish" and "non_git_cwd_release_blocked" in release_blockers:
        reasons.append("publish_from_non_git_cwd_blocked")
    if raw_secret_marker_detected:
        reasons.append("raw_secret_marker_detected")
    return tuple(reasons)


def _has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
