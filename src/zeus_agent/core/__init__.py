"""Core orchestration logic for Zeus."""

from .approvals import approve_run, reject_run, run_status
from .blueprint import BlueprintBundle, build_blueprint
from .mneme import diff_gate, list_evidence, record_evidence
from .registry import add_model_route, add_provider, create_github_publish_plan, register_tool
from .skills import draft_skill, promote_skill, retire_skill, test_skill


def pursue_run(*args, **kwargs):
    """Lazy wrapper to avoid importing the agent session during package init."""

    from .sisyphus import pursue_run as _pursue_run

    return _pursue_run(*args, **kwargs)

__all__ = [
    "BlueprintBundle",
    "add_model_route",
    "add_provider",
    "approve_run",
    "build_blueprint",
    "create_github_publish_plan",
    "diff_gate",
    "draft_skill",
    "list_evidence",
    "promote_skill",
    "pursue_run",
    "record_evidence",
    "register_tool",
    "reject_run",
    "run_status",
    "retire_skill",
    "test_skill",
]
