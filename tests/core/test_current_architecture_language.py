from __future__ import annotations

import re
from pathlib import Path
from typing import Final


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
# README left this set at the control-plane refoundation: the 12-pillar core
# language is ARCHIVED branding, kept only inside the archived master-plan
# records below. tests/test_docs_domain_language.py pins that the README
# family never reintroduces it.
CURRENT_ARCHITECTURE_DOCS: Final[tuple[Path, ...]] = (
    PROJECT_ROOT / "docs/hermes-grade-platform-master-design.md",
    PROJECT_ROOT / "docs/hermes-live-platform-absorption-master-plan.md",
)
APPROVED_CORE_NAMES: Final[tuple[str, ...]] = (
    "Zeus Kernel",
    "Athena",
    "Thunderbolt",
    "Aegis",
    "Mercury",
    "Apollo",
    "Hephaestus",
    "Poseidon",
    "Artemis",
    "Demeter",
    "Olympus",
    "Prometheus",
)
FORBIDDEN_MYTH_PILLARS: Final[tuple[str, ...]] = (
    "Hera",
    "Hades",
    "Dionysus",
    "Ares",
)
ACTIVE_ZEUS_LIVE_CLAIMS: Final[tuple[str, ...]] = (
    "Zeus live provider execution is active",
    "Zeus live MCP execution is active",
    "Zeus live web execution is active",
    "Zeus live gateway delivery is active",
    "Zeus live browser execution is active",
    "Zeus live plugin execution is active",
    "Zeus live network execution is active",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _core_language_section(text: str) -> str:
    pattern = re.compile(
        r"^## (?:Reduced Zeus Core Language|Zeus Core Language|Canonical Terms)\n(?P<body>.*?)(?=^##\s|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    assert match is not None, "missing core language section"
    return match.group("body")


def _pillar_names_from_table(section: str) -> tuple[str, ...]:
    names: list[str] = []
    for line in section.splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or cells[0] in {"Product name", "Term", "---"}:
            continue
        names.append(cells[0])
    return tuple(names)


def test_current_architecture_docs_use_reduced_core_language() -> None:
    # Given: current architecture docs are the active explanatory source.
    current_text_by_path = {path: _read(path) for path in CURRENT_ARCHITECTURE_DOCS}

    for path, text in current_text_by_path.items():
        # When: each current doc is inspected for the reduced core language section.
        reduced_section = _core_language_section(text)
        section_names = _pillar_names_from_table(reduced_section)

        # Then: each doc names exactly the approved product-domain layer.
        assert section_names[: len(APPROVED_CORE_NAMES)] == APPROVED_CORE_NAMES, path
        assert "Hermes remains upstream/reference only" in text, path
        assert "Mercury is the Zeus internal transport product name" in text, path

        # Then: current docs do not promote live-capable surfaces to active Zeus execution.
        for claim in ACTIVE_ZEUS_LIVE_CLAIMS:
            assert claim not in text, (path, claim)
        assert "designed/prepared/dry-run/future" in text or "not implemented production status" in text, path

        # Then: forbidden mythology terms are not canonical pillars.
        for name in FORBIDDEN_MYTH_PILLARS:
            active_pattern = re.compile(rf"\|\s*{re.escape(name)}\s*\|")
            assert active_pattern.search(text) is None, (path, name)
