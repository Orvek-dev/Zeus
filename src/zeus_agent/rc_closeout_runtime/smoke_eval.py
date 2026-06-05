from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, JsonValue


SmokeDecision = Literal["report", "blocked"]

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


@dataclass(frozen=True)
class RequiredSuite:
    suite_id: str
    test_files: tuple[str, ...]


class RcSmokeSuiteCheck(BaseModel):
    model_config = _MODEL_CONFIG

    suite_id: str
    present: bool
    test_files: tuple[str, ...]
    missing_files: tuple[str, ...] = ()


class RcSmokeEvalResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: SmokeDecision
    suite: str
    total: int
    passed: int
    failed: int
    missing_suite_count: int
    required_suite_ids: tuple[str, ...]
    missing_suite_ids: tuple[str, ...] = ()
    checks: tuple[RcSmokeSuiteCheck, ...]
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")

    def with_secret_scan(self) -> RcSmokeEvalResult:
        serialized = json.dumps(self.to_payload(), sort_keys=True).lower()
        safe = not any(marker in serialized for marker in _SECRET_MARKERS)
        return self.model_copy(update={"no_secret_echo": safe})


_REQUIRED_SUITES: Final[tuple[RequiredSuite, ...]] = (
    RequiredSuite("provider_api_session", ("test_wave21_entry_provider_api.py",)),
    RequiredSuite("tool_catalog", ("test_wave22_tool_catalog.py",)),
    RequiredSuite("memory_wiki", ("test_wave23_memory_wiki_runtime.py",)),
    RequiredSuite("plugin_quarantine", ("test_wave24_plugin_runtime.py",)),
    RequiredSuite("trajectory_export", ("test_wave25_trajectory_runtime.py",)),
    RequiredSuite("batch_runner", ("test_wave26_batch_runtime.py",)),
    RequiredSuite("acp_adapter", ("test_wave27_acp_runtime.py",)),
    RequiredSuite("mcp_catalog", ("test_wave28_mcp_catalog.py",)),
    RequiredSuite("cron_guard", ("test_wave29_cron_runtime.py",)),
    RequiredSuite("review_runtime", ("test_wave30_review_runtime.py",)),
    RequiredSuite("golden_journeys", ("test_wave34_golden_journeys.py",)),
    RequiredSuite("workflow_ulw", ("test_wave31_adaptive_workflow.py", "test_wave202_workflow_critique_checkpoint.py")),
    RequiredSuite("wave20_observability", ("test_wave20_observability_gates.py",)),
    RequiredSuite("rc_docs_sync", ("test_wave205_current_docs_sync.py",)),
    RequiredSuite("rc_coverage_audit", ("test_wave206_rc_coverage_audit.py",)),
)


def build_rc_smoke_eval(
    *,
    root: Path | None = None,
    excluded_suite_ids: tuple[str, ...] = (),
) -> RcSmokeEvalResult:
    project_root = Path.cwd() if root is None else root
    checks = tuple(_check_suite(project_root, suite, excluded_suite_ids) for suite in _REQUIRED_SUITES)
    missing_suite_ids = tuple(check.suite_id for check in checks if not check.present)
    failed = len(missing_suite_ids)
    total = len(checks)
    result = RcSmokeEvalResult(
        decision="blocked" if failed else "report",
        suite="w205_w212_rc_smoke",
        total=total,
        passed=total - failed,
        failed=failed,
        missing_suite_count=failed,
        required_suite_ids=tuple(suite.suite_id for suite in _REQUIRED_SUITES),
        missing_suite_ids=missing_suite_ids,
        checks=checks,
        credential_material_accessed=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        live_production_claimed=False,
    )
    return result.with_secret_scan()


def _check_suite(
    root: Path,
    suite: RequiredSuite,
    excluded_suite_ids: tuple[str, ...],
) -> RcSmokeSuiteCheck:
    if suite.suite_id in excluded_suite_ids:
        return RcSmokeSuiteCheck(
            suite_id=suite.suite_id,
            present=False,
            test_files=suite.test_files,
            missing_files=suite.test_files,
        )
    missing = tuple(file_name for file_name in suite.test_files if not (root / "tests" / file_name).exists())
    return RcSmokeSuiteCheck(
        suite_id=suite.suite_id,
        present=not missing,
        test_files=suite.test_files,
        missing_files=missing,
    )
