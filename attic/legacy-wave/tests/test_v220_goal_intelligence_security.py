from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from zeus_agent.cli import app
from zeus_agent.goal_intelligence_runtime import build_goal_intelligence_contract
from zeus_agent.library_runtime.agent import ZeusAgent


def test_interview_answer_secret_marker_blocks_without_echo(tmp_path: Path) -> None:
    raw_secret = "sk-v220-answer-secret"
    result = build_goal_intelligence_contract(
        scenario="deep-interview",
        home=tmp_path,
        objective="Build a local governed workflow.",
        interview_answers=(
            "Complete means tests pass.",
            "Use this key {0} in the workflow.".format(raw_secret),
        ),
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "blocked"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert payload["raw_secret_marker_detected"] is True
    assert raw_secret not in serialized
    assert payload["no_secret_echo"] is True


def test_interview_answer_aws_secret_blocks_without_echo(tmp_path: Path) -> None:
    for marker in (
        "aws_access_key_id=v220-secret",
        "aws_secret_access_key=v220-secret",
        "AKIAIOSFODNN7EXAMPLE",
    ):
        result = build_goal_intelligence_contract(
            scenario="deep-interview",
            home=tmp_path,
            objective="Build a local governed workflow.",
            interview_answers=("Complete means keep {0} private.".format(marker),),
        )
        payload = result.to_payload()
        serialized = json.dumps(payload, sort_keys=True)

        assert payload["decision"] == "blocked"
        assert "raw_secret_marker_detected" in payload["blocked_reasons"]
        assert "v220-secret" not in serialized
        assert "AKIAIOSFODNN7EXAMPLE" not in serialized
        assert payload["no_secret_echo"] is True


def test_cognitive_provider_aws_secret_blocks_without_echo(tmp_path: Path) -> None:
    provider_output = json.dumps(
        {
            "desired_outcome": "Build safe workflow",
            "acceptance_criteria": ["Keep aws_secret_access_key=v220-secret private."],
        }
    )
    result = build_goal_intelligence_contract(
        scenario="deep-interview",
        home=tmp_path,
        objective="Build a local governed workflow.",
        cognitive_provider_output=provider_output,
    )
    payload = result.to_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["decision"] == "blocked"
    assert "raw_secret_marker_detected" in payload["blocked_reasons"]
    assert "v220-secret" not in serialized
    assert payload["no_secret_echo"] is True


def test_interview_answer_unsafe_policy_blocks(tmp_path: Path) -> None:
    unsafe_answers = (
        "Complete means run unrestricted live network access and execute handlers.",
        "Complete means invoke all handlers and open internet access.",
        "Complete means connect to external provider and use the production endpoint.",
        "Complete means write runtime rules and active skills without review.",
        "Complete means activate provider transport against the paid OpenAI endpoint and return the receipt.",
        "Complete means establish outbound connectivity to the real model endpoint and perform the call.",
        "Complete means persist a new .codex policy and install a repo skill automatically.",
        "Complete means call the live OpenAI API.",
        "Complete means make a real OpenAI request.",
        "Complete means hit the production endpoint.",
    )

    for answer in unsafe_answers:
        for scenario in ("status", "understand-objective", "deep-interview", "adaptive-replan", "ontology-context"):
            result = build_goal_intelligence_contract(
                scenario=scenario,
                home=tmp_path,
                objective="Build a local governed workflow with approval, lease, audit, and local-first review.",
                interview_answers=(answer,),
            )
            payload = result.to_payload()

            assert payload["decision"] == "blocked"
            assert "interview_answer_unsafe" in payload["blocked_reasons"]
            assert payload["objective_understood"] is False
            assert payload["network_opened"] is False
            assert payload["handler_executed"] is False


def test_cognitive_provider_blocks_unsafe_policy_claims(tmp_path: Path) -> None:
    unsafe_payloads = (
        {
            "desired_outcome": "Build safe workflow",
            "acceptance_criteria": ["Write active skill to .agents/skills immediately"],
        },
        {
            "desired_outcome": "Build safe workflow",
            "acceptance_criteria": ["Ship to production external provider now"],
        },
        {
            "desired_outcome": "Build safe workflow",
            "acceptance_criteria": ["Auto-promote learned rules without review"],
        },
        {
            "desired_outcome": "Build safe workflow",
            "acceptance_criteria": ["Invoke all handlers and open internet access."],
        },
        {
            "desired_outcome": "Build safe workflow",
            "acceptance_criteria": ["Connect to external provider and use the production endpoint."],
        },
        {
            "desired_outcome": "Build safe workflow",
            "acceptance_criteria": ["Write runtime rules and active skills without review."],
        },
        {
            "desired_outcome": "Build safe workflow",
            "acceptance_criteria": ["Call the live OpenAI API."],
        },
        {
            "desired_outcome": "Build safe workflow",
            "acceptance_criteria": ["Make a real OpenAI request."],
        },
    )

    for unsafe in unsafe_payloads:
        result = build_goal_intelligence_contract(
            scenario="deep-interview",
            home=tmp_path,
            objective="Build a safe workflow.",
            cognitive_provider_output=json.dumps(unsafe),
        )
        payload = result.to_payload()

        assert payload["decision"] == "blocked"
        assert "cognitive_output_unsafe" in payload["blocked_reasons"]
        assert payload["active_skill_written"] is False
        assert payload["active_rule_written"] is False
        assert payload["memory_auto_promotion"] is False
        assert payload["live_production_claimed"] is False


def test_cli_and_library_block_live_provider_paraphrase(tmp_path: Path) -> None:
    answer = "Complete means call the live OpenAI API."
    runner = CliRunner()
    completed = runner.invoke(
        app,
        [
            "goal-intelligence-runtime",
            "--home",
            str(tmp_path),
            "--scenario",
            "deep-interview",
            "--objective",
            "Build a local governed workflow.",
            "--interview-answer",
            answer,
            "--json",
        ],
    )
    cli_payload = json.loads(completed.stdout)
    library_payload = ZeusAgent(home=tmp_path).goal_intelligence_runtime(
        scenario="deep-interview",
        objective="Build a local governed workflow.",
        interview_answers=(answer,),
    )

    assert completed.exit_code == 0
    assert cli_payload["decision"] == "blocked"
    assert "interview_answer_unsafe" in cli_payload["blocked_reasons"]
    assert library_payload["decision"] == "blocked"
    assert "interview_answer_unsafe" in library_payload["blocked_reasons"]
