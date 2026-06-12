from __future__ import annotations

import json

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.cognitive_provider_activation_runtime import build_cognitive_provider_activation_contract
from zeus_agent.library_runtime.agent import ZeusAgent
from zeus_agent.model_runtime import ProviderMessage, ProviderMetadataEntry, ProviderRegistry
from zeus_agent.model_runtime import ProviderRuntimeRequest
from zeus_agent.release_gated_ulw_runtime import build_release_gated_ulw_status
from zeus_agent.runtime_lease import RuntimeLease


def test_v310_release_gate_reports_intelligence_to_live_platform_checkpoint() -> None:
    payload = build_release_gated_ulw_status(target_version="v3.1.0").to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v3.1.0"
    assert payload["release_stage"] == "intelligence_to_live_execution_platform"
    assert payload["cognitive_provider_activation_contract_available"] is True
    assert payload["model_runtime_goal_intelligence_bridge_available"] is True
    assert payload["intent_output_schema_gate_available"] is True
    assert payload["governed_live_thin_slice_available"] is True
    assert payload["production_ready"] is False
    assert payload["next_version"] == "v4.0.0"


def test_fake_provider_outputs_intent_json_only_when_schema_metadata_is_requested() -> None:
    lease = _lease()
    default = ProviderRegistry().generate(_request(intent_schema=False), lease, now=lease.issued_at)
    cognitive = ProviderRegistry().generate(_request(intent_schema=True), lease, now=lease.issued_at)
    parsed = json.loads(cognitive.content)

    assert default.content == "fake provider dry-run response"
    assert cognitive.decision == "selected"
    assert parsed["desired_outcome"].startswith("제우스야")
    assert parsed["acceptance_criteria"]
    assert cognitive.network_opened is False


def test_cognitive_provider_activation_bridges_provider_output_to_goal_intelligence() -> None:
    payload = build_cognitive_provider_activation_contract(
        scenario="fake-provider-intent",
        objective="제우스야, plan a governed coding workflow with evidence.",
    ).to_payload()

    assert payload["decision"] == "report"
    assert payload["target_version"] == "v3.1.0"
    assert payload["provider_runtime_invoked"] is True
    assert payload["cognitive_provider_used"] is True
    assert payload["intent_frame_validated"] is True
    assert payload["goal_intelligence_contract_ready"] is True
    assert payload["workloop_bridge_available"] is True
    assert payload["network_opened"] is False
    assert payload["handler_executed"] is False


def test_cognitive_provider_activation_blocks_external_and_unsafe_output() -> None:
    external = build_cognitive_provider_activation_contract(scenario="external-provider-block").to_payload()
    unsafe = build_cognitive_provider_activation_contract(scenario="unsafe-output-block").to_payload()

    assert external["decision"] == "blocked"
    assert external["provider_runtime_invoked"] is False
    assert external["network_opened"] is False
    assert "external_provider_requires_explicit_credential_scope" in external["blocked_reasons"]
    assert unsafe["decision"] == "blocked"
    assert "cognitive_output_unsafe" in unsafe["blocked_reasons"]
    assert unsafe["live_production_claimed"] is False


def test_cognitive_provider_activation_cli_and_library_match() -> None:
    runner = CliRunner()
    completed = runner.invoke(
        app,
        [
            "cognitive-provider-activation",
            "--scenario",
            "fake-provider-intent",
            "--objective",
            "제우스야, turn my objective into a safe workflow.",
            "--json",
        ],
    )
    library_payload = ZeusAgent().cognitive_provider_activation_runtime(
        scenario="fake-provider-intent",
        objective="제우스야, turn my objective into a safe workflow.",
    )

    assert completed.exit_code == 0, completed.stdout
    cli_payload = json.loads(completed.stdout)
    assert cli_payload["target_version"] == library_payload["target_version"]
    assert cli_payload["cognitive_provider_activation_ready"] is True
    assert library_payload["cognitive_provider_activation_ready"] is True


def _request(*, intent_schema: bool) -> ProviderRuntimeRequest:
    metadata = (ProviderMetadataEntry(key="zeus.intent_schema", value=True),) if intent_schema else ()
    return ProviderRuntimeRequest(
        provider_kind="fake",
        provider_id="fake.cognitive",
        model_id="fake.intent",
        messages=(ProviderMessage(role="user", content="제우스야, build a governed workflow."),),
        metadata=metadata,
        evidence_target="mneme.v310.cognitive_provider",
    )


def _lease() -> RuntimeLease:
    return RuntimeLease(
        lease_id="v310.lease.test",
        objective_id="v310.objective.test",
        principal_id="v310.principal.test",
        run_id="v310.run.test",
        allowed_capabilities=("provider.fake.generate",),
        budget_limit=16,
        evidence_target="mneme.v310.cognitive_provider",
    )
