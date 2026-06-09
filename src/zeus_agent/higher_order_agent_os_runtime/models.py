from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue, field_validator

HigherOrderAgentOsDecision = Literal["report", "blocked"]
HigherOrderAgentOsScenario = Literal["status", "operator-cockpit", "public-boundary"]

_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0} must be non-empty".format(field_name))
    return normalized


class HigherOrderAgentOsResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: HigherOrderAgentOsDecision
    target_version: Literal["v6.0.0"] = "v6.0.0"
    scenario: HigherOrderAgentOsScenario
    blocked_reasons: tuple[str, ...] = ()
    zeus_call_response: str = "네, 제우스입니다."
    higher_order_agent_os_ready: bool = False
    objective_compiler_workflow_ready: bool = False
    governed_live_connector_platform_ready: bool = False
    tui_cockpit_ready: bool = False
    recursive_improvement_review_ready: bool = False
    plugin_ecosystem_skeleton_ready: bool = False
    remote_sandbox_contract_ready: bool = False
    tenant_auth_contract_ready: bool = False
    eval_dashboard_contract_ready: bool = False
    persistent_audit_contract_ready: bool = False
    operator_commands: tuple[str, ...] = ()
    tui_panels: tuple[str, ...] = ()
    plugin_contracts: tuple[str, ...] = ()
    sandbox_contracts: tuple[str, ...] = ()
    auth_contracts: tuple[str, ...] = ()
    learning_contracts: tuple[str, ...] = ()
    remote_sandbox_enabled: bool = False
    multi_user_hosted_enabled: bool = False
    unattended_execution_enabled: bool = False
    memory_auto_promotion: bool = False
    production_ready: bool = False
    network_opened: bool = False
    credential_material_accessed: bool = False
    external_delivery_opened: bool = False
    handler_executed: bool = False
    live_production_claimed: bool = False
    no_secret_echo: bool = True

    @field_validator(
        "blocked_reasons",
        "operator_commands",
        "tui_panels",
        "plugin_contracts",
        "sandbox_contracts",
        "auth_contracts",
        "learning_contracts",
    )
    @classmethod
    def _validate_text_tuple(cls, values: tuple[str, ...], info: object) -> tuple[str, ...]:
        return tuple(_require_non_empty(value, info.field_name) for value in values)

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
