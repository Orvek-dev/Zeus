from __future__ import annotations

from pathlib import Path
from typing import Final


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]


def test_default_product_suite_excludes_legacy_wave_attic() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package_root = PROJECT_ROOT / "src/zeus_agent"
    eval_root = package_root / "eval"

    active_wave_sources = tuple(package_root.glob("wave*.py"))
    active_wave_evals = tuple(eval_root.glob("wave*.py"))
    active_legacy_cli = tuple(package_root.glob("cli_wave*.py")) + (
        package_root / "cli.py",
    )
    top_level_wave_tests = tuple((PROJECT_ROOT / "tests").glob("test_wave*.py"))

    assert 'testpaths = ["tests/core", "tests/conformance"]' in pyproject
    assert 'extend-exclude = ["attic"]' in pyproject
    assert (PROJECT_ROOT / "attic/legacy-wave/README.md").exists()
    assert active_wave_sources == ()
    assert active_wave_evals == ()
    assert top_level_wave_tests == ()
    assert all(not path.exists() for path in active_legacy_cli)


def test_python_module_entrypoint_uses_product_cli() -> None:
    entrypoint = (PROJECT_ROOT / "src/zeus_agent/__main__.py").read_text(encoding="utf-8")

    assert "from zeus_agent.cli_main import app" in entrypoint
    assert "from zeus_agent.cli import app" not in entrypoint
