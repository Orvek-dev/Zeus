from __future__ import annotations

from pathlib import Path
from typing import Final

import zeus_agent


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]


def test_exported_package_version_matches_project_metadata() -> None:
    project_version = _project_version(PROJECT_ROOT / "pyproject.toml")

    assert project_version == "5.5.0"
    assert zeus_agent.__version__ == project_version


def _project_version(path: Path) -> str:
    in_project_section = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == "[project]":
            in_project_section = True
            continue
        if line.startswith("[") and in_project_section:
            break
        if in_project_section and line.startswith("version = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise AssertionError("missing [project] version")
