from __future__ import annotations

import json
from typing import Any, Optional

from zeus_agent.adaptive_zeus_runtime import build_adaptive_zeus_contract
from zeus_agent.ontology_cockpit_runtime import OntologyCockpitRuntime
from zeus_agent.memory_ontology_surface_runtime import build_memory_ontology_surface_contract
from zeus_agent.orchestration_runtime import WorkflowCompileRequest
from zeus_agent.persona_cockpit_runtime import PersonaCockpitRuntime
from zeus_agent.platform_cockpit_runtime import PlatformCockpitRuntime
from zeus_agent.plugin_cockpit_runtime import PluginCockpitRuntime
from zeus_agent.real_execution_runtime import build_real_execution_contract
from zeus_agent.real_memory_operation_runtime import build_real_memory_operation_contract
from zeus_agent.real_mcp_runtime import build_real_mcp_contract
from zeus_agent.real_platform_runtime import build_real_platform_contract
from zeus_agent.real_provider_runtime import build_real_provider_contract
from zeus_agent.research_cockpit_runtime import ResearchCockpitRuntime
from zeus_agent.skill_cockpit_runtime import SkillCockpitRuntime
from zeus_agent.skill_eval_registry_runtime import SkillEvalRegistryRuntime
from zeus_agent.skill_eval_runtime import SkillEvalRuntime
from zeus_agent.skill_eval_runtime import SkillEvalResult
from zeus_agent.skill_learning_runtime import SkillLearningMemoryRuntime
from zeus_agent.skill_learning_runtime import SkillLearningRuntime
from zeus_agent.workflow_learning_runtime import WorkflowCritiqueMemoryRuntime


class GrowthFacadeMixin:
    def plugin_status(self, *, plugin_id: Optional[str] = None) -> dict[str, Any]:
        return PluginCockpitRuntime().build(plugin_id=plugin_id).to_payload()

    def skill_status(self, *, candidate_id: Optional[str] = None) -> dict[str, Any]:
        return SkillCockpitRuntime(self.home).build(candidate_id=candidate_id).to_payload()

    def skill_eval(self, *, candidate_id: str) -> dict[str, Any]:
        return SkillEvalRuntime(self.home).evaluate(candidate_id=candidate_id).to_payload()

    def skill_eval_record(self, *, eval_result: dict[str, Any], eval_ref: str) -> dict[str, Any]:
        return SkillEvalRegistryRuntime(self.home).record(
            eval_result=SkillEvalResult.model_validate_json(json.dumps(eval_result)),
            eval_ref=eval_ref,
        ).to_payload()

    def skill_eval_records(self) -> dict[str, Any]:
        return SkillEvalRegistryRuntime(self.home).list().to_payload()

    def skill_learnings(self, *, candidate_id: Optional[str] = None) -> dict[str, Any]:
        return SkillLearningRuntime(self.home).build(candidate_id=candidate_id).to_payload()

    def skill_learning_memory_record(self, *, candidate_id: str) -> dict[str, Any]:
        return SkillLearningMemoryRuntime(self.home).record(candidate_id=candidate_id).to_payload()

    def workflow_critique_memory_record(
        self,
        *,
        objective: str,
        task_count: int = 1,
        requires_code: bool = False,
        requires_research: bool = False,
        risk_level: str = "normal",
        evidence_target: str = "mneme.library.workflow_critique",
    ) -> dict[str, Any]:
        request = WorkflowCompileRequest(
            objective=objective,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
            evidence_target=evidence_target,
        )
        return WorkflowCritiqueMemoryRuntime(self.home).record(request=request).to_payload()

    def ontology_status(self, *, candidate_id: Optional[str] = None) -> dict[str, Any]:
        return OntologyCockpitRuntime(self.home).build(candidate_id=candidate_id).to_payload()

    def memory_ontology_status(
        self,
        *,
        subject: Optional[str] = None,
        candidate_id: Optional[str] = None,
    ) -> dict[str, Any]:
        return build_memory_ontology_surface_contract(
            home=self.home,
            subject=subject,
            candidate_id=candidate_id,
        ).to_payload()

    def adaptive_zeus_status(
        self,
        *,
        objective: str,
        task_count: int = 1,
        requires_code: bool = False,
        requires_research: bool = False,
        risk_level: str = "normal",
        evidence_target: str = "v010.adaptive_zeus",
    ) -> dict[str, Any]:
        return build_adaptive_zeus_contract(
            objective=objective,
            task_count=task_count,
            requires_code=requires_code,
            requires_research=requires_research,
            risk_level=risk_level,
            evidence_target=evidence_target,
        ).to_payload()

    def platform_status(self, *, surface_id: Optional[str] = None) -> dict[str, Any]:
        return PlatformCockpitRuntime().build(surface_id=surface_id).to_payload()

    def research_status(
        self,
        *,
        source_id: Optional[str] = None,
        query: str = "agent workflow research",
        objective_id: str = "library.research",
    ) -> dict[str, Any]:
        return ResearchCockpitRuntime().build(
            source_id=source_id,
            query=query,
            objective_id=objective_id,
        ).to_payload()

    def persona_status(self, *, profile: Optional[str] = None) -> dict[str, Any]:
        return PersonaCockpitRuntime(self.home).build(profile=profile).to_payload()

    def provider_runtime(
        self,
        *,
        scenario: str = "status",
        endpoint: str = "https://api.openai.local/v1/chat/completions",
        allowed_host: str = "api.openai.local",
        secret_ref: str = "env://ZEUS_V110_PROVIDER_KEY",
        model_id: str = "gpt-v110-provider",
        message: str = "summarize Zeus real provider runtime",
        budget_limit: int = 8,
        budget_requested: int = 2,
        timeout_ms: int = 1500,
    ) -> dict[str, Any]:
        return build_real_provider_contract(
            scenario=scenario,
            endpoint=endpoint,
            allowed_host=allowed_host,
            secret_ref=secret_ref,
            model_id=model_id,
            message=message,
            budget_limit=budget_limit,
            budget_requested=budget_requested,
            timeout_ms=timeout_ms,
        ).to_payload()

    def mcp_runtime(
        self,
        *,
        scenario: str = "status",
        server_id: str = "mcp.github",
        include_tools: tuple[str, ...] = (),
        exclude_tools: tuple[str, ...] = (),
        resources_requested: bool = False,
        prompts_requested: bool = False,
        source_pinned: bool = True,
        description: str = "Pinned MCP server manifest for governed Zeus runtime.",
    ) -> dict[str, Any]:
        return build_real_mcp_contract(
            scenario=scenario,
            server_id=server_id,
            include_tools=include_tools,
            exclude_tools=exclude_tools,
            resources_requested=resources_requested,
            prompts_requested=prompts_requested,
            source_pinned=source_pinned,
            description=description,
        ).to_payload()

    def platform_runtime(
        self,
        *,
        scenario: str = "status",
    ) -> dict[str, Any]:
        return build_real_platform_contract(scenario=scenario).to_payload()

    def execution_runtime(
        self,
        *,
        scenario: str = "status",
        command: str = "pwd",
    ) -> dict[str, Any]:
        return build_real_execution_contract(scenario=scenario, command=command).to_payload()

    def memory_operation(
        self,
        *,
        scenario: str = "status",
        subject: str = "Zeus",
    ) -> dict[str, Any]:
        return build_real_memory_operation_contract(
            scenario=scenario,
            home=self.home,
            subject=subject,
        ).to_payload()
