from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue


SecurityDecision = Literal["report", "blocked"]

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
_PRIVATE_IGNORE_PATHS: Final[tuple[str, ...]] = (
    ".agents/",
    ".codex/",
    ".omo/",
    "AGENTS.md",
    "ETHOS.md",
    "docs/ai/",
    "gstack/",
    "harness/",
    "plans/",
    "scripts/harness/",
    "spec/",
    "templates/",
    "evidence/",
)
_PUBLIC_DOC_PATHS: Final[tuple[str, ...]] = (
    "README.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "docs/live-connection-architecture.md",
    "docs/zeus-hermes-live-opt-in-boundary.md",
)


class RcSecurityBoundaryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: SecurityDecision
    private_ignore_paths: tuple[str, ...]
    private_ignore_count: int
    missing_private_ignores: tuple[str, ...]
    private_boundary_passed: bool
    public_document_paths: tuple[str, ...]
    release_blockers: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    public_release_blocked: bool
    git_metadata_present: bool
    raw_secret_marker_detected: bool
    security_review_required: bool = True
    independent_review_required: bool = True
    credential_material_accessed: bool = False
    network_opened: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RcSecurityBoundaryResult:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})


def build_rc_security_boundary(
    *,
    root: Optional[Path] = None,
    extra_public_text: Optional[str] = None,
) -> RcSecurityBoundaryResult:
    project_root = Path.cwd() if root is None else root
    gitignore_text = _read_text(project_root / ".gitignore")
    missing_ignores = tuple(path for path in _PRIVATE_IGNORE_PATHS if path not in gitignore_text)
    raw_secret_marker_detected = _has_secret_marker(extra_public_text or "")
    blocked_reasons = _blocked_reasons(missing_ignores, raw_secret_marker_detected)
    release_blockers = _release_blockers(project_root)
    result = RcSecurityBoundaryResult(
        decision="blocked" if blocked_reasons else "report",
        private_ignore_paths=_PRIVATE_IGNORE_PATHS,
        private_ignore_count=len(_PRIVATE_IGNORE_PATHS) - len(missing_ignores),
        missing_private_ignores=missing_ignores,
        private_boundary_passed=len(missing_ignores) == 0,
        public_document_paths=_existing_public_docs(project_root),
        release_blockers=release_blockers,
        blocked_reasons=blocked_reasons,
        public_release_blocked=bool(release_blockers),
        git_metadata_present=(project_root / ".git").is_dir(),
        raw_secret_marker_detected=raw_secret_marker_detected,
        security_review_required=True,
        independent_review_required=True,
        credential_material_accessed=False,
        network_opened=False,
        external_delivery_opened=False,
        handler_executed=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _blocked_reasons(missing_ignores: tuple[str, ...], raw_secret_marker_detected: bool) -> tuple[str, ...]:
    reasons = []
    if missing_ignores:
        reasons.append("missing_private_ignore_boundary")
    if raw_secret_marker_detected:
        reasons.append("raw_secret_marker_detected")
    return tuple(reasons)


def _release_blockers(root: Path) -> tuple[str, ...]:
    blockers = ["production_live_surface_evidence_required", "project_mode_release_gate_required"]
    if not (root / ".git").is_dir():
        blockers.append("non_git_cwd_release_blocked")
    return tuple(blockers)


def _existing_public_docs(root: Path) -> tuple[str, ...]:
    return tuple(path for path in _PUBLIC_DOC_PATHS if (root / path).is_file())


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _has_secret_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)
