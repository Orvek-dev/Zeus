"""Blueprint generation.

This first implementation is deterministic on purpose. Zeus should be useful
before model routing exists, and its persisted specs should stay inspectable.
LLM-based elicitation can later replace individual inference functions without
changing the contract/storage surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from pathlib import Path
from uuid import uuid4

from zeus_agent.schemas.execution_spec import (
    BudgetSpec,
    ExecutionSpec,
    ExecutionStep,
    SandboxSpec,
    VerificationRule,
    WorkspaceSpec,
)
from zeus_agent.schemas.goal_contract import GoalContract, RiskLevel
from zeus_agent.security.redaction import redact_text

HIGH_RISK_TERMS = (
    "production",
    "prod",
    "deploy",
    "payment",
    "billing",
    "customer data",
    "delete",
    "remove all",
    "rm -rf",
    "drop table",
    "credential",
    "secret",
    "password",
    "token",
    "api key",
    "git push",
    "publish",
    "upload",
    "release",
    "운영",
    "배포",
    "결제",
    "고객 데이터",
    "삭제",
    "시크릿",
    "토큰",
    "비밀번호",
    "깃헙에 올",
)

MEDIUM_RISK_TERMS = (
    "api",
    "mcp",
    "network",
    "internet",
    "browser",
    "scrape",
    "automation",
    "automate",
    "docker",
    "container",
    "video",
    "image generation",
    "file write",
    "external",
    "워크플로우",
    "자동화",
    "외부",
    "브라우저",
    "검색",
    "비디오",
    "영상",
)


@dataclass(frozen=True)
class BlueprintBundle:
    goal_contract: GoalContract
    execution_spec: ExecutionSpec
    redaction_summary: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "goal_contract": self.goal_contract.model_dump(mode="json"),
            "execution_spec": self.execution_spec.model_dump(mode="json"),
            "redaction_summary": self.redaction_summary,
        }


def build_blueprint(user_request: str, *, workspace: Path | None = None) -> BlueprintBundle:
    redacted_request = redact_text(user_request)
    request = redacted_request.value.strip()
    normalized_goal = _normalize_goal(request)
    risk_level = _infer_risk_level(request)
    workspace_root = (workspace or Path.cwd()).expanduser().resolve()
    goal_id = _new_id("goal", request)
    run_id = _new_id("run", f"{goal_id}:{request}")
    deliverables = _infer_deliverables(request)
    acceptance_criteria = _acceptance_criteria(deliverables)
    constraints = _default_constraints()

    goal_contract = GoalContract(
        goal_id=goal_id,
        raw_user_request=request,
        normalized_goal=normalized_goal,
        deliverables=deliverables,
        acceptance_criteria=acceptance_criteria,
        assumptions=_infer_assumptions(request),
        constraints=constraints,
        risk_level=risk_level,
        requires_human_approval=True,
        approval_state="pending_approval",
        forbidden_actions=_default_forbidden_actions(),
        allowed_paths=[str(workspace_root)],
        sensitive_input_redacted=redacted_request.redacted,
        redaction_findings=list(redacted_request.findings),
    )

    execution_spec = ExecutionSpec(
        run_id=run_id,
        goal_contract_id=goal_id,
        status="awaiting_approval",
        execution_mode="plan_only",
        workspace=WorkspaceSpec(
            root=str(workspace_root),
            allowed_paths=[str(workspace_root)],
            forbidden_paths=_default_forbidden_paths(),
        ),
        sandbox=SandboxSpec(
            isolation="none",
            network_policy="deny_by_default",
            network_allowlist=[],
            snapshot_required=True,
        ),
        budgets=_budgets_for(risk_level),
        tools_required=_infer_tools(request),
        steps=_execution_steps(risk_level),
        verification_rules=_verification_rules(),
        stop_conditions=[
            "All acceptance criteria have direct evidence.",
            "The verifier reports no unresolved required checks.",
            "The user rejects or supersedes the blueprint.",
            "A budget, policy, or safety limit is reached.",
        ],
        escalation_conditions=[
            "The implementation requires credentials, external writes, or network access.",
            "The observed codebase contradicts a goal-contract assumption.",
            "The same failure repeats after two repair attempts.",
            "The requested outcome cannot be verified from local evidence.",
        ],
    )

    return BlueprintBundle(
        goal_contract=goal_contract,
        execution_spec=execution_spec,
        redaction_summary={
            "redacted": redacted_request.redacted,
            "findings": list(redacted_request.findings),
        },
    )


def _new_id(prefix: str, seed: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(f"{timestamp}:{seed}:{uuid4().hex}".encode()).hexdigest()[:12]
    return f"{prefix}_{timestamp}_{digest}"


def _normalize_goal(request: str) -> str:
    text = " ".join(request.split())
    if len(text) <= 240:
        return text
    return f"{text[:237]}..."


def _infer_risk_level(request: str) -> RiskLevel:
    lowered = request.lower()
    if any(term in lowered for term in HIGH_RISK_TERMS):
        return "high"
    if any(term in lowered for term in MEDIUM_RISK_TERMS):
        return "medium"
    return "low"


def _infer_deliverables(request: str) -> list[str]:
    lowered = request.lower()
    deliverables = ["goal_contract", "execution_spec", "verification_report"]
    if any(term in lowered for term in ("app", "web", "dashboard", "site", "ui", "앱", "웹", "대시보드")):
        deliverables.extend(["source_changes", "run_instructions"])
    if any(term in lowered for term in ("automation", "automate", "workflow", "자동화", "워크플로우")):
        deliverables.extend(["automation_workflow", "operator_controls"])
    if any(term in lowered for term in ("marketing", "carousel", "campaign", "마케팅", "캐러셀", "캠페인")):
        deliverables.extend(["creative_brief", "content_production_pipeline"])
    if any(term in lowered for term in ("data", "csv", "analysis", "report", "데이터", "분석", "리포트")):
        deliverables.extend(["analysis_artifacts", "result_summary"])
    return list(dict.fromkeys(deliverables))


def _acceptance_criteria(deliverables: list[str]) -> list[str]:
    criteria = [
        "A GoalContract exists with explicit deliverables, assumptions, constraints, and forbidden actions.",
        "An ExecutionSpec exists and remains plan-only until human approval.",
        "Every deliverable is paired with at least one verification rule or required evidence item.",
        "No external write, destructive action, credential use, or network access occurs before approval.",
    ]
    for deliverable in deliverables:
        criteria.append(f"The '{deliverable}' deliverable is produced or explicitly marked out of scope.")
    return criteria


def _infer_assumptions(request: str) -> list[str]:
    assumptions = [
        "The current local workspace is the intended project boundary unless the user selects another workspace.",
        "Zeus should ask for approval before any implementation or external action.",
    ]
    lowered = request.lower()
    if any(term in lowered for term in ("api", "mcp", "external", "외부")):
        assumptions.append("External integrations are design-only until credentials and network policy are approved.")
    if any(term in lowered for term in ("marketing", "carousel", "마케팅", "캐러셀")):
        assumptions.append("Trend research and media generation require a separate network/tool approval gate.")
    return assumptions


def _default_constraints() -> list[str]:
    return [
        "Local-first: persist state under ZEUS_HOME only.",
        "Blueprint-first: execution cannot start until the user approves the plan.",
        "Evidence-first: completion claims must cite observable artifacts, tests, or command results.",
        "Secrets are redacted before persistence.",
        "Hermes state must not be modified by Zeus.",
    ]


def _default_forbidden_actions() -> list[str]:
    return [
        "Modify ~/.hermes or any Hermes runtime state.",
        "Read or persist raw secrets from .env, keychains, SSH keys, browser profiles, or credential stores.",
        "Run destructive filesystem commands without a reversible checkpoint and explicit approval.",
        "Push to GitHub, deploy, publish, purchase, email, or message external parties without explicit approval.",
        "Open network access outside an approved allowlist.",
    ]


def _default_forbidden_paths() -> list[str]:
    return [
        "~/.hermes",
        "~/.ssh",
        "~/.gnupg",
        "~/.aws",
        "~/.config/gh",
        "**/.env",
        "**/.env.*",
        "**/*id_rsa*",
        "**/*id_ed25519*",
    ]


def _budgets_for(risk_level: RiskLevel) -> BudgetSpec:
    if risk_level == "high":
        return BudgetSpec(max_wall_clock_seconds=600, max_tool_calls=40, max_cost_usd=0.0)
    if risk_level == "medium":
        return BudgetSpec(max_wall_clock_seconds=900, max_tool_calls=60, max_cost_usd=0.0)
    return BudgetSpec(max_wall_clock_seconds=1200, max_tool_calls=80, max_cost_usd=0.0)


def _infer_tools(request: str) -> list[str]:
    lowered = request.lower()
    tools = ["filesystem_read", "blueprint_writer", "event_log"]
    if any(term in lowered for term in ("code", "app", "web", "repo", "코드", "앱", "웹")):
        tools.extend(["filesystem_write_after_approval", "shell_after_approval", "test_runner"])
    if any(term in lowered for term in ("api", "mcp", "external", "search", "trend", "외부", "검색", "트렌드")):
        tools.extend(["network_after_allowlist_approval", "integration_registry"])
    if any(term in lowered for term in ("automation", "workflow", "자동화", "워크플로우")):
        tools.extend(["workflow_builder", "approval_gate"])
    return list(dict.fromkeys(tools))


def _execution_steps(risk_level: RiskLevel) -> list[ExecutionStep]:
    return [
        ExecutionStep(
            step_id="step_1_intent_lock",
            title="Lock Intent",
            intent="Confirm the goal contract and keep uncertain requirements as explicit assumptions.",
            actions=[
                "Read the approved GoalContract.",
                "Map each deliverable to acceptance criteria.",
                "Stop if approval is missing or the contract is rejected.",
            ],
            expected_evidence=["approved GoalContract", "deliverable-to-criteria map"],
            risk_level="low",
        ),
        ExecutionStep(
            step_id="step_2_readonly_inspection",
            title="Read-only Inspection",
            intent="Inspect the local workspace without changing files.",
            actions=[
                "Inventory relevant files and project commands.",
                "Record observations in the event log.",
                "Detect conflicts with constraints or forbidden paths.",
            ],
            expected_evidence=["workspace inventory", "constraint check result"],
            risk_level="low",
        ),
        ExecutionStep(
            step_id="step_3_sandbox_plan",
            title="Sandbox Plan",
            intent="Prepare an implementation plan that can run in a controlled sandbox.",
            actions=[
                "Select the smallest viable implementation path.",
                "Define reversible checkpoints.",
                "Define verification commands before writes.",
            ],
            expected_evidence=["implementation plan", "checkpoint plan", "verification command list"],
            risk_level=risk_level,
        ),
        ExecutionStep(
            step_id="step_4_controlled_implementation",
            title="Controlled Implementation",
            intent="Apply changes only inside approved paths and only after the approval gate.",
            actions=[
                "Create a checkpoint.",
                "Apply scoped file edits.",
                "Record changed files and rationale.",
            ],
            expected_evidence=["checkpoint id", "changed file list", "diff summary"],
            risk_level=risk_level,
            requires_approval=True,
        ),
        ExecutionStep(
            step_id="step_5_verification_and_report",
            title="Verification and Report",
            intent="Prove completion from observed evidence before claiming done.",
            actions=[
                "Run syntax, behavior, acceptance, and security checks.",
                "Repair only when evidence shows the fix path.",
                "Produce a final report with residual risks.",
            ],
            expected_evidence=["test output", "acceptance checklist", "final report"],
            risk_level="medium" if risk_level == "high" else risk_level,
        ),
    ]


def _verification_rules() -> list[VerificationRule]:
    return [
        VerificationRule(
            rule_id="verify_syntax",
            level="syntax",
            description="The produced artifacts parse, typecheck, build, or otherwise load successfully.",
            evidence_required=["command output or parser result"],
        ),
        VerificationRule(
            rule_id="verify_behavior",
            level="behavior",
            description="The implementation behavior is tested or manually exercised in the sandbox.",
            evidence_required=["test output", "runtime observation"],
        ),
        VerificationRule(
            rule_id="verify_acceptance",
            level="acceptance",
            description="Every GoalContract acceptance criterion is checked against evidence.",
            evidence_required=["acceptance checklist"],
        ),
        VerificationRule(
            rule_id="verify_security",
            level="security",
            description="The run does not persist secrets, touch forbidden paths, or exceed approved network policy.",
            evidence_required=["secret scan result", "path policy result", "network policy result"],
        ),
        VerificationRule(
            rule_id="verify_human_gate",
            level="human_review",
            description="Execution starts only after a human approval record exists.",
            evidence_required=["approval record"],
        ),
    ]
