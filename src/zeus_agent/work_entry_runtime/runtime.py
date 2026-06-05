from __future__ import annotations

from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

from zeus_agent.live_dry_run_runtime import LiveDryRunResult, LiveDryRunRuntime
from zeus_agent.objective_runtime import ObjectiveCompiler, ZeusObjectiveContract
from zeus_agent.orchestration_runtime import DynamicWorkflowCompiler, DynamicWorkflowPlan, WorkflowCompileRequest

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class WorkEntryResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: str
    profile: str
    objective_contract: ZeusObjectiveContract
    workflow_plan: DynamicWorkflowPlan
    live_preview: Optional[LiveDryRunResult] = None
    blocked_reasons: tuple[str, ...]
    recommended_next_commands: tuple[str, ...]
    objective_mode_active: bool = True
    execution_allowed: bool = False
    authority_granted: bool = False
    live_transport_enabled: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    credential_material_accessed: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class WorkEntryRuntime:
    def plan(
        self,
        *,
        objective: str,
        task_count: int = 1,
        requires_code: bool = False,
        requires_research: bool = False,
        risk_level: str = "normal",
        evidence_target: str = "mneme.work.entry",
        surface_id: Optional[str] = None,
        principal_id: str = "local.operator",
        delivery_target: Optional[str] = None,
        allowlisted_delivery_targets: tuple[str, ...] = (),
    ) -> WorkEntryResult:
        objective_contract = ObjectiveCompiler().compile(objective)
        workflow_plan = DynamicWorkflowCompiler().compile(
            WorkflowCompileRequest(
                objective=objective,
                task_count=task_count,
                requires_code=requires_code,
                requires_research=requires_research,
                risk_level=_risk_level(risk_level),
                evidence_target=evidence_target,
            ),
        )
        blocked_reasons = tuple(
            dict.fromkeys([*objective_contract.block_reasons, *workflow_plan.blocked_reasons])
        )
        if objective_contract.blocked or workflow_plan.decision == "blocked":
            return _result(
                objective_contract=objective_contract,
                workflow_plan=workflow_plan,
                blocked_reasons=blocked_reasons,
            )

        live_preview: Optional[LiveDryRunResult] = None
        live_reasons: tuple[str, ...] = ()
        if surface_id is not None:
            live_preview = LiveDryRunRuntime().run(
                surface_id=surface_id,
                principal_id=principal_id,
                objective_id=objective_contract.objective_id,
                delivery_target=delivery_target,
                allowlisted_delivery_targets=allowlisted_delivery_targets,
            )
            live_reasons = tuple("live_preview:{0}".format(reason) for reason in live_preview.blocked_reasons)

        return _result(
            objective_contract=objective_contract,
            workflow_plan=workflow_plan,
            live_preview=live_preview,
            blocked_reasons=live_reasons,
        )


def _risk_level(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"low", "normal", "high"}:
        return normalized
    return "normal"


def _result(
    *,
    objective_contract: ZeusObjectiveContract,
    workflow_plan: DynamicWorkflowPlan,
    blocked_reasons: tuple[str, ...],
    live_preview: Optional[LiveDryRunResult] = None,
) -> WorkEntryResult:
    decision = "blocked" if blocked_reasons else "planned"
    result = WorkEntryResult(
        decision=decision,
        profile="work",
        objective_contract=objective_contract,
        workflow_plan=workflow_plan,
        live_preview=live_preview,
        blocked_reasons=blocked_reasons,
        recommended_next_commands=_recommended_next_commands(decision, live_preview),
        execution_allowed=False,
        authority_granted=False,
        live_transport_enabled=False,
        network_opened=_live_network_opened(live_preview),
        handler_executed=_live_handler_executed(live_preview),
        external_delivery_opened=_live_external_delivery_opened(live_preview),
        credential_material_accessed=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result)})


def _recommended_next_commands(
    decision: str,
    live_preview: Optional[LiveDryRunResult],
) -> tuple[str, ...]:
    if decision == "blocked":
        return ("zeus security --json", "zeus persona --profile strict --json")
    if live_preview is not None:
        return ("zeus live-dry-run --json", "zeus live --json", "zeus security --json")
    return ("zeus workflow --json", "zeus live --json", "zeus security --json")


def _live_network_opened(live_preview: Optional[LiveDryRunResult]) -> bool:
    return bool(live_preview.network_opened if live_preview is not None else False)


def _live_handler_executed(live_preview: Optional[LiveDryRunResult]) -> bool:
    return bool(live_preview.handler_executed if live_preview is not None else False)


def _live_external_delivery_opened(live_preview: Optional[LiveDryRunResult]) -> bool:
    return bool(live_preview.external_delivery_opened if live_preview is not None else False)


def _no_secret_echo(result: WorkEntryResult) -> bool:
    blob = result.model_dump_json().lower()
    return not any(
        marker in blob
        for marker in (
            "sk-wave",
            "ghp_",
            "github_pat_",
            "glpat-",
            "xoxb-",
            "xoxa-",
            "xoxp-",
            "token=sk",
            "password=",
            "secret=sk",
            "private_key",
            "-----begin",
        )
    )
