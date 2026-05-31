from zeus_agent.core.blueprint import build_blueprint


def test_blueprint_is_plan_only_and_redacts_sensitive_input(tmp_path):
    bundle = build_blueprint(
        "Build a web automation workflow with api_key=supersecretvalue",
        workspace=tmp_path,
    )

    contract = bundle.goal_contract
    spec = bundle.execution_spec

    assert contract.approval_state == "pending_approval"
    assert contract.requires_human_approval is True
    assert contract.sensitive_input_redacted is True
    assert "supersecretvalue" not in contract.raw_user_request
    assert spec.execution_mode == "plan_only"
    assert spec.status == "awaiting_approval"
    assert spec.workspace.allowed_paths == [str(tmp_path.resolve())]
    assert any(step.requires_approval for step in spec.steps)


def test_blueprint_infers_marketing_workflow_deliverables(tmp_path):
    bundle = build_blueprint(
        "마케팅 캐러셀 자동화 워크플로우를 만들고 싶어",
        workspace=tmp_path,
    )

    deliverables = set(bundle.goal_contract.deliverables)
    assert "automation_workflow" in deliverables
    assert "creative_brief" in deliverables
    assert "content_production_pipeline" in deliverables
    assert bundle.goal_contract.risk_level == "medium"
