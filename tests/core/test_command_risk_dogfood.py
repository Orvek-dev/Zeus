from __future__ import annotations

from zeus_agent.capability_registry_runtime import SideEffectClass
from zeus_agent.command_risk_runtime import classify_command
from zeus_agent.trust_loop_runtime import ActionRisk, Reversibility


def test_dogfood_read_only_environment_probe_stays_read_only() -> None:
    risk = classify_command(
        "pwd && printf '\\n---\\n' && git status --short --branch && "
        "printf '\\n---\\n' && git remote -v"
    )

    assert risk.side_effect is SideEffectClass.none
    assert risk.reversibility is Reversibility.reversible
    assert risk.risk is ActionRisk.low


def test_dogfood_read_only_file_listing_pipeline_stays_read_only() -> None:
    risk = classify_command(
        "find . -maxdepth 2 -type f \\( -perm -111 -o -name '*.py' "
        "-o -name '*.sh' \\) | sort | sed 's#^./##' | head -200"
    )

    assert risk.side_effect is SideEffectClass.none
    assert risk.reversibility is Reversibility.reversible
    assert risk.risk is ActionRisk.low


def test_dogfood_python_module_diagnostics_stay_read_only() -> None:
    for command in (
        "python -V && printf '\\n---\\n' && pytest --version",
        "python --version && printf '\\n---\\n' && pytest --collect-only -q",
        "python -m pytest --collect-only -q",
        "python -m zeus_agent.cli_main --help",
        ".venv/bin/python -m zeus_agent --help",
        "/usr/local/bin/python3.12 -m zeus_agent.cli_main --help",
        "python -m src.zeus_agent --help",
        "python -m pip show zeus-agent || true",
        "python -m pip list && printf '\\n---\\n' && python -m pip check || true",
        "python -m pip show zeus-agent pytest hatchling 2>/dev/null || true && "
        "printf '\\n---\\n' && python -m pip list --format=columns | head -40",
        "python -m zeus_agent.cli_main --help 2>&1 || true && printf '\\n---\\n' && "
        "python -m zeus_agent.cli_main connect --help 2>&1 || true",
        "python --version && printf '\\n---\\n' && python -m pytest --version && "
        "printf '\\n---\\n' && python -m zeus_agent --help",
        "pwd && printf '\\n---\\n' && git status --short --branch && printf '\\n---\\n' && "
        "python --version && printf '\\n---\\n' && command -v pytest || true && "
        "printf '\\n---\\n' && command -v hermes || true && printf '\\n---\\n' && "
        "command -v python || true",
    ):
        risk = classify_command(command)
        assert risk.side_effect is SideEffectClass.none, command
        assert risk.reversibility is Reversibility.reversible, command
        assert risk.risk is ActionRisk.low, command


def test_compileall_is_local_write_not_external() -> None:
    risk = classify_command("python -m compileall -q src")

    assert risk.side_effect is SideEffectClass.local_write
    assert risk.reversibility is Reversibility.compensable
    assert risk.risk is ActionRisk.medium
    assert "python_module_local_write" in risk.reasons
