from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Optional

from zeus_agent.rc_closeout_runtime.models import MacroWaveCoverage
from zeus_agent.rc_closeout_runtime.models import RcCoverageAuditResult


@dataclass(frozen=True)
class MacroWaveSpec:
    wave_id: str
    title: str
    source_dirs: tuple[str, ...]
    test_terms: tuple[str, ...]
    evidence_terms: tuple[str, ...]


_WAVE_RE: Final = re.compile(r"zeus-w(?P<wave>\d+)-|test_wave(?P<test_wave>\d+)_")
_REMAINING_CHECKPOINTS: Final[tuple[str, ...]] = (
    "W206",
    "W207",
    "W208",
    "W209",
    "W210",
    "W211",
    "W212",
)
_BOUNDARY_NOTES: Final[tuple[str, ...]] = (
    "W205-W212 are local micro checkpoints, not official macro design waves.",
    "The official macro target remains Wave 9: Zeus Live Platform Release Candidate.",
    "Public releases can report source/test coverage without private plans or evidence artifacts.",
    "RC evidence can prove dry-run and beta breadth; production-ready live surfaces need separate opt-in proof.",
)
_SPECS: Final[tuple[MacroWaveSpec, ...]] = (
    MacroWaveSpec(
        wave_id="W1",
        title="Product Shell And Zeus Entry",
        source_dirs=("entry_runtime", "setup_runtime", "doctor_runtime", "work_entry_runtime"),
        test_terms=("entry_provider_api", "chat_entry", "work_entry", "golden_journeys"),
        evidence_terms=("live-beta", "live-readiness", "golden", "entry"),
    ),
    MacroWaveSpec(
        wave_id="W2",
        title="Provider, API, And Session Core",
        source_dirs=("model_runtime", "api_runtime", "session_runtime", "model_settings_runtime"),
        test_terms=("provider", "api", "session", "model_settings"),
        evidence_terms=("provider", "api", "session", "credential"),
    ),
    MacroWaveSpec(
        wave_id="W3",
        title="Tool Registry And MCP Expansion",
        source_dirs=("tool_runtime", "tool_cockpit_runtime", "mcp_runtime", "mcp_cockpit_runtime"),
        test_terms=("tool", "mcp"),
        evidence_terms=("tool", "mcp"),
    ),
    MacroWaveSpec(
        wave_id="W4",
        title="Gateway And Delivery",
        source_dirs=("gateway_runtime", "gateway_cockpit_runtime", "gateway_pairing_runtime"),
        test_terms=("gateway",),
        evidence_terms=("gateway",),
    ),
    MacroWaveSpec(
        wave_id="W5",
        title="MemoryGraph, Wiki, Skills",
        source_dirs=(
            "memory_graph_runtime",
            "memory_cockpit_runtime",
            "wiki_runtime",
            "ontology_runtime",
            "skill_evolution",
            "skill_eval_runtime",
            "skill_learning_runtime",
        ),
        test_terms=("memory", "wiki", "ontology", "skill"),
        evidence_terms=("memory", "ontology", "skill"),
    ),
    MacroWaveSpec(
        wave_id="W6",
        title="Research, Browser, Terminal, Sandbox",
        source_dirs=(
            "research_runtime",
            "web_runtime",
            "github_runtime",
            "browser_runtime",
            "terminal_runtime",
            "sandbox_runtime",
        ),
        test_terms=("research", "browser", "terminal", "sandbox"),
        evidence_terms=("research", "browser", "terminal", "sandbox"),
    ),
    MacroWaveSpec(
        wave_id="W7",
        title="Parallel ULW And Objective OS",
        source_dirs=("objective_runtime", "orchestration_runtime", "workloop_runtime", "verification_runtime"),
        test_terms=("objective", "workflow", "review", "orchestration"),
        evidence_terms=("workflow", "review", "orchestration"),
    ),
    MacroWaveSpec(
        wave_id="W8",
        title="ACP, Cron, Plugins, Trajectories",
        source_dirs=("acp_runtime", "workflow_runtime", "plugin_runtime", "trajectory_runtime", "batch_runtime"),
        test_terms=("acp", "cron", "plugin", "trajectory", "batch"),
        evidence_terms=("acp", "cron", "plugin", "trajectory", "batch"),
    ),
    MacroWaveSpec(
        wave_id="W9",
        title="Zeus Live Platform Release Candidate",
        source_dirs=("eval", "platform_cockpit_runtime", "live_readiness_runtime", "security_cockpit_runtime"),
        test_terms=("golden", "platform", "security", "live_readiness", "wave205"),
        evidence_terms=("golden", "platform", "security", "w205", "release"),
    ),
)


class RcCoverageAuditRuntime:
    def __init__(self, root: Path) -> None:
        self.root = root

    def build(self, *, macro_wave_id: Optional[str] = None) -> RcCoverageAuditResult:
        coverage = tuple(self._coverage_for(spec) for spec in _SPECS)
        selected = _select(coverage, macro_wave_id)
        reasons = _blocked_reasons(macro_wave_id=macro_wave_id, selected=selected)
        decision = "blocked" if reasons else "report"
        result = RcCoverageAuditResult(
            decision=decision,
            macro_wave_count=len(coverage),
            macro_waves=coverage,
            selected_macro_wave=selected,
            latest_micro_wave=self._latest_baseline_micro_wave(),
            remaining_checkpoints=_REMAINING_CHECKPOINTS,
            blocked_reasons=reasons,
            boundary_notes=_BOUNDARY_NOTES,
            hard_close_ready=False,
            credential_material_accessed=False,
            network_opened=False,
            handler_executed=False,
            live_production_claimed=False,
        )
        return result.with_secret_scan()

    def _coverage_for(self, spec: MacroWaveSpec) -> MacroWaveCoverage:
        source_count = _count_existing_dirs(self.root / "src/zeus_agent", spec.source_dirs)
        test_count = _count_matching_files(self.root / "tests", "test_*.py", spec.test_terms)
        evidence_count = _count_matching_files(self.root / "evidence", "zeus-w*.txt", spec.evidence_terms)
        missing = _missing_requirements(source_count, test_count, evidence_count)
        return MacroWaveCoverage(
            wave_id=spec.wave_id,
            title=spec.title,
            source_dir_count=source_count,
            test_file_count=test_count,
            evidence_file_count=evidence_count,
            status=_status_for(missing),
            missing_requirements=missing,
        )

    def _latest_baseline_micro_wave(self) -> Optional[int]:
        evidence_dir = self.root / "evidence"
        test_dir = self.root / "tests"
        waves: list[int] = []
        for path in tuple(evidence_dir.glob("zeus-w*.txt")) + tuple(test_dir.glob("test_wave*.py")):
            match = _WAVE_RE.search(path.name)
            if match is None:
                continue
            raw = match.group("wave") or match.group("test_wave")
            wave = int(raw)
            if wave <= 205:
                waves.append(wave)
        if not waves:
            return None
        return max(waves)


def _blocked(reasons: tuple[str, ...]) -> RcCoverageAuditResult:
    return RcCoverageAuditResult(
        decision="blocked",
        macro_wave_count=0,
        macro_waves=(),
        latest_micro_wave=None,
        remaining_checkpoints=_REMAINING_CHECKPOINTS,
        blocked_reasons=reasons,
        boundary_notes=_BOUNDARY_NOTES,
        hard_close_ready=False,
        credential_material_accessed=False,
        network_opened=False,
        handler_executed=False,
        live_production_claimed=False,
    ).with_secret_scan()


def _select(
    coverage: tuple[MacroWaveCoverage, ...],
    macro_wave_id: Optional[str],
) -> Optional[MacroWaveCoverage]:
    if macro_wave_id is None:
        return None
    return next((wave for wave in coverage if wave.wave_id == macro_wave_id), None)


def _blocked_reasons(
    *,
    macro_wave_id: Optional[str],
    selected: Optional[MacroWaveCoverage],
) -> tuple[str, ...]:
    if macro_wave_id is not None and selected is None:
        return ("unknown_macro_wave",)
    return ()


def _count_existing_dirs(root: Path, names: tuple[str, ...]) -> int:
    return sum(1 for name in names if (root / name).is_dir())


def _count_matching_files(root: Path, pattern: str, terms: tuple[str, ...]) -> int:
    if not root.is_dir():
        return 0
    return sum(1 for path in root.glob(pattern) if _matches_any(path.name, terms))


def _matches_any(value: str, terms: tuple[str, ...]) -> bool:
    lowered = value.lower()
    return any(term in lowered for term in terms)


def _missing_requirements(
    source_count: int,
    test_count: int,
    evidence_count: int,
) -> tuple[str, ...]:
    missing: list[str] = []
    if source_count == 0:
        missing.append("missing_source_surface")
    if test_count == 0:
        missing.append("missing_test_surface")
    if evidence_count == 0:
        missing.append("missing_evidence_surface")
    return tuple(missing)


def _status_for(missing: tuple[str, ...]) -> str:
    if not missing:
        return "covered"
    if len(missing) == 3:
        return "missing"
    return "partial"
