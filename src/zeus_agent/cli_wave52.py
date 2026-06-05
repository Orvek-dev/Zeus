from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from pydantic import JsonValue

from zeus_agent.skill_cockpit_runtime import SkillCockpitRuntime
from zeus_agent.skill_eval_registry_runtime import SkillEvalRegistryRuntime
from zeus_agent.skill_eval_runtime import SkillEvalRuntime
from zeus_agent.skill_eval_runtime import SkillEvalResult
from zeus_agent.skill_learning_runtime import SkillLearningMemoryRuntime
from zeus_agent.skill_learning_runtime import SkillLearningRuntime


def register_wave52_commands(app: typer.Typer) -> None:
    @app.command("skills")
    def skills(
        home: Optional[Path] = typer.Option(None, "--home"),
        candidate_id: Optional[str] = typer.Option(None, "--candidate-id"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = SkillCockpitRuntime(home).build(candidate_id=candidate_id)
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("skill-eval")
    def skill_eval(
        candidate_id: str = typer.Option(..., "--candidate-id"),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = SkillEvalRuntime(home).evaluate(candidate_id=candidate_id)
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("skill-eval-record")
    def skill_eval_record(
        eval_json: str = typer.Option(..., "--eval-json"),
        eval_ref: str = typer.Option(..., "--eval-ref"),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = SkillEvalRegistryRuntime(home or Path.cwd()).record(
            eval_result=SkillEvalResult.model_validate_json(eval_json),
            eval_ref=eval_ref,
        )
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("skill-eval-records")
    def skill_eval_records(
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = SkillEvalRegistryRuntime(home or Path.cwd()).list()
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("skill-learnings")
    def skill_learnings(
        home: Optional[Path] = typer.Option(None, "--home"),
        candidate_id: Optional[str] = typer.Option(None, "--candidate-id"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = SkillLearningRuntime(home or Path.cwd()).build(candidate_id=candidate_id)
        _print_payload(result.to_payload(), as_json=as_json)

    @app.command("skill-learning-memory-record")
    def skill_learning_memory_record(
        candidate_id: str = typer.Option(..., "--candidate-id"),
        home: Optional[Path] = typer.Option(None, "--home"),
        as_json: bool = typer.Option(False, "--json"),
    ) -> None:
        result = SkillLearningMemoryRuntime(home or Path.cwd()).record(candidate_id=candidate_id)
        _print_payload(result.to_payload(), as_json=as_json)


def _print_payload(payload: dict[str, JsonValue], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(payload))
    else:
        typer.echo(json.dumps(payload, indent=2))
