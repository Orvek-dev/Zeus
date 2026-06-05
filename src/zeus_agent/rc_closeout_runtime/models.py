from __future__ import annotations

import json
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue


CoverageStatus = Literal["covered", "partial", "missing"]
CoverageDecision = Literal["report", "blocked"]

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
    "private-key",
    "-----begin",
)


class MacroWaveCoverage(BaseModel):
    model_config = _MODEL_CONFIG

    wave_id: str
    title: str
    source_dir_count: int
    test_file_count: int
    evidence_file_count: int
    status: CoverageStatus
    missing_requirements: tuple[str, ...] = ()


class RcCoverageAuditResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: CoverageDecision
    macro_wave_count: int
    macro_waves: tuple[MacroWaveCoverage, ...]
    selected_macro_wave: Optional[MacroWaveCoverage] = None
    latest_micro_wave: Optional[int] = None
    remaining_checkpoints: tuple[str, ...] = ()
    blocked_reasons: tuple[str, ...] = ()
    boundary_notes: tuple[str, ...]
    hard_close_ready: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RcCoverageAuditResult:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})
