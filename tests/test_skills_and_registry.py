from zeus_agent.core.registry import (
    add_model_route,
    add_provider,
    create_github_publish_plan,
    list_github_publish_plans,
    list_model_routes,
    list_tools,
    provider_status,
    register_tool,
)
from zeus_agent.core.skills import (
    draft_skill,
    list_skills,
    promote_skill,
    retire_skill,
    test_skill,
)


def test_skill_lifecycle(tmp_path):
    home = tmp_path / "zeus-home"
    manifest = draft_skill(
        "Carousel Research",
        "Research repeatable carousel production patterns.",
        triggers=["marketing carousel", "creative workflow"],
        procedure=(
            "Read the approved GoalContract. Identify expected deliverables. "
            "Collect evidence for trend claims. Produce a verification checklist. "
            "Stop if external network or credential access is required without approval."
        ),
        home=home,
    )

    tested = test_skill(manifest.skill_id, home=home)
    promoted = promote_skill(manifest.skill_id, home=home)
    retired = retire_skill(manifest.skill_id, home=home)

    assert tested.evaluation and tested.evaluation.passed is True
    assert promoted.state == "promoted"
    assert retired.state == "retired"
    assert list_skills(home=home)[0]["skill_id"] == manifest.skill_id


def test_provider_model_tool_and_github_registry(tmp_path, monkeypatch):
    home = tmp_path / "zeus-home"
    monkeypatch.setenv("ZEUS_TEST_KEY", "present")

    provider = add_provider("test-provider", "ZEUS_TEST_KEY", home=home)
    route = add_model_route("planning", "test-provider", "test-model", home=home)
    tool = register_tool("local-test", "Local test runner.", risk_level="low", home=home)
    plan = create_github_publish_plan("Orvek-dev/Zeus", home=home)

    assert provider.env_var == "ZEUS_TEST_KEY"
    assert provider_status(home=home)[0]["configured"] is True
    assert list_model_routes(home=home)[0].route_id == route.route_id
    assert list_tools(home=home)[0].tool_id == tool.tool_id
    assert list_github_publish_plans(home=home)[0].plan_id == plan.plan_id
    assert plan.ready is False
