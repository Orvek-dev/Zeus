from __future__ import annotations

import json
from pathlib import Path
from typing import Final, Literal, Optional

from pydantic import BaseModel, ConfigDict, JsonValue


MetricStatus = Literal["met", "gap"]

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


class RcMetricTarget(BaseModel):
    model_config = _MODEL_CONFIG

    metric_id: str
    actual: int
    target: int
    status: MetricStatus


class RcSourceMetricsResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: Literal["report"]
    python_file_count: int
    python_pure_loc: int
    test_file_count: int
    evidence_file_count: int
    runtime_package_count: int
    cli_wave_module_count: int
    targets: tuple[RcMetricTarget, ...]
    target_gap_count: int
    gap_metric_ids: tuple[str, ...]
    metrics_reported: bool = True
    hermes_parity_claimed: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RcSourceMetricsResult:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})


def build_rc_source_metrics(*, root: Optional[Path] = None) -> RcSourceMetricsResult:
    project_root = Path.cwd() if root is None else root
    src_root = project_root / "src/zeus_agent"
    python_files = tuple(src_root.rglob("*.py")) if src_root.is_dir() else ()
    python_pure_loc = sum(_pure_loc(path) for path in python_files)
    test_file_count = _glob_count(project_root / "tests", "test_*.py")
    evidence_file_count = _glob_count(project_root / "evidence", "zeus-w*.txt")
    runtime_package_count = _runtime_package_count(src_root)
    cli_wave_module_count = _glob_count(src_root, "cli_wave*.py")
    targets = _targets(
        python_file_count=len(python_files),
        python_pure_loc=python_pure_loc,
        test_file_count=test_file_count,
        evidence_file_count=evidence_file_count,
        runtime_package_count=runtime_package_count,
        cli_wave_module_count=cli_wave_module_count,
    )
    gap_metric_ids = tuple(target.metric_id for target in targets if target.status == "gap")
    result = RcSourceMetricsResult(
        decision="report",
        python_file_count=len(python_files),
        python_pure_loc=python_pure_loc,
        test_file_count=test_file_count,
        evidence_file_count=evidence_file_count,
        runtime_package_count=runtime_package_count,
        cli_wave_module_count=cli_wave_module_count,
        targets=targets,
        target_gap_count=len(gap_metric_ids),
        gap_metric_ids=gap_metric_ids,
        metrics_reported=True,
        hermes_parity_claimed=False,
        credential_material_accessed=False,
        network_opened=False,
        handler_executed=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _pure_loc(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if _is_pure_line(line))


def _is_pure_line(line: str) -> bool:
    stripped = line.strip()
    return stripped != "" and not stripped.startswith("#")


def _glob_count(root: Path, pattern: str) -> int:
    if not root.is_dir():
        return 0
    return len(tuple(root.glob(pattern)))


def _runtime_package_count(src_root: Path) -> int:
    if not src_root.is_dir():
        return 0
    return sum(1 for path in src_root.iterdir() if path.is_dir() and _is_runtime_package(path.name))


def _is_runtime_package(name: str) -> bool:
    return name.endswith("_runtime") or name.endswith("_cockpit_runtime") or name in _DIRECT_RUNTIME_PACKAGES


_DIRECT_RUNTIME_PACKAGES: Final[tuple[str, ...]] = (
    "acp_runtime",
    "api_runtime",
    "batch_runtime",
    "gateway_runtime",
    "mcp_runtime",
    "plugin_runtime",
    "tool_runtime",
    "trajectory_runtime",
    "workflow_runtime",
)


def _targets(
    *,
    python_file_count: int,
    python_pure_loc: int,
    test_file_count: int,
    evidence_file_count: int,
    runtime_package_count: int,
    cli_wave_module_count: int,
) -> tuple[RcMetricTarget, ...]:
    return (
        _target("runtime_files", python_file_count, 700),
        _target("python_pure_loc", python_pure_loc, 120_000),
        _target("test_files", test_file_count, 500),
        _target("public_private_evidence_files", evidence_file_count, 0),
        _target("runtime_packages", runtime_package_count, 100),
        _target("cli_wave_modules", cli_wave_module_count, 100),
    )


def _target(metric_id: str, actual: int, target: int) -> RcMetricTarget:
    return RcMetricTarget(
        metric_id=metric_id,
        actual=actual,
        target=target,
        status="met" if actual >= target else "gap",
    )
