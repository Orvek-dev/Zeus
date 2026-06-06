from __future__ import annotations

import re
from pathlib import Path
from typing import Final


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
PUBLIC_DOCS: Final[tuple[Path, ...]] = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "docs/hermes-comparison.md",
    PROJECT_ROOT / "docs/live-connection-architecture.md",
)
PUBLIC_MASTER_PLAN_DOCS: Final[tuple[Path, ...]] = (
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
ACTIVE_LIVE_CLAIMS: Final[tuple[str, ...]] = (
    "Zeus live provider execution is active",
    "Zeus live MCP execution is active",
    "Zeus live web execution is active",
    "Zeus live gateway delivery is active",
    "Zeus live browser execution is active",
    "Zeus live plugin execution is active",
    "Zeus live network execution is active",
)
STALE_PUBLIC_EVIDENCE_MARKERS: Final[tuple[str, ...]] = (
    "tests-244",
    "244%20passed",
    "`244` public tests passed",
    "244 public tests",
    "tests-294",
    "`294` public tests passed",
    "tests-296",
    "296%20passed",
    "`296` public tests passed",
    "296 public tests",
    "tests-484",
    "484%20passed",
    "`484` public tests passed",
    "484 public tests",
    "tests-1229",
    "1229%20passed",
    "`1229` public tests passed",
    "1229 public tests",
    "tests-1230%20passed",
    "`1230` public tests passed",
    "1230 public tests",
    "tests-1234%20passed",
    "`1234` public tests passed",
    "1234 public tests",
    "tests-1237%20passed",
    "`1237` public tests passed",
    "1237 public tests",
    "tests-1238%20passed",
    "`1238` public tests passed",
    "1238 public tests",
    "tests-1242%20passed",
    "`1242` public tests passed",
    "1242 public tests",
    "tests-1324%20passed",
    "`1324` public tests passed",
    "1324 public tests",
    "tests-1243%20passed",
    "`1243` public tests passed",
    "1243 public tests",
    "tests-1247%20passed",
    "`1247` public tests passed",
    "1247 public tests",
    "tests-1251%20passed",
    "`1251` public tests passed",
    "1251 public tests",
    "tests-1256%20passed",
    "`1256` public tests passed",
    "1256 public tests",
    "tests-1261%20passed",
    "`1261` public tests passed",
    "1261 public tests",
    "tests-1262%20passed",
    "`1262` public tests passed",
    "1262 public tests",
    "tests-1266%20passed",
    "`1266` public tests passed",
    "1266 public tests",
    "tests-1271%20passed",
    "`1271` public tests passed",
    "1271 public tests",
    "tests-1276%20passed",
    "`1276` public tests passed",
    "1276 public tests",
    "tests-1288%20passed",
    "`1288` public tests passed",
    "1288 public tests",
    "tests-1294%20passed",
    "`1294` public tests passed",
    "1294 public tests",
    "tests-1301%20passed",
    "`1301` public tests passed",
    "1301 public tests",
    "tests-1308%20passed",
    "`1308` public tests passed",
    "1308 public tests",
    "tests-1314%20passed",
    "`1314` public tests passed",
    "1314 public tests",
    "tests-1320%20passed",
    "`1320` public tests passed",
    "1320 public tests",
    "tests-1362%20passed",
    "`1362` public tests passed",
    "1362 public tests",
    "tests-1370%20passed",
    "`1370` public tests passed",
    "1370 public tests",
    "tests-1372%20passed",
    "`1372` public tests passed",
    "1372 public tests",
    "tests-1381%20passed",
    "`1381` public tests passed",
    "1381 public tests",
    "tests-1389%20passed",
    "`1389` public tests passed",
    "1389 public tests",
    "`8/8` checks passed",
    "8/8 total",
)
CURRENT_PUBLIC_EVIDENCE_MARKERS: Final[tuple[str, ...]] = (
    "tests-1398%20passed",
    "`1398` public tests passed",
    "`10/10` checks passed",
    "`9/9` checks passed",
)
REQUIRED_RUNTIME_ANCHORS: Final[dict[str, tuple[str, ...]]] = {
    "Zeus Kernel": ("objective_runtime", "verification_runtime"),
    "Athena": ("objective_runtime",),
    "Thunderbolt": ("runtime_lease",),
    "Aegis": ("security_runtime",),
    "Mercury": ("transport_runtime", "connector_runtime"),
    "Apollo": ("model_runtime", "provider_runtime"),
    "Hephaestus": ("tool_runtime",),
    "Poseidon": ("gateway_runtime",),
    "Artemis": ("research_runtime",),
    "Demeter": ("ontology_runtime",),
    "Olympus": ("orchestration_runtime",),
    "Prometheus": ("skill_evolution",),
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^{re.escape(heading)}\n(?P<body>.*?)(?=^##\s|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    assert match is not None, f"missing section: {heading}"
    return match.group("body")


def _pillar_names_from_table(section: str) -> tuple[str, ...]:
    names: list[str] = []
    for line in section.splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or cells[0] in {"Product name", "---"}:
            continue
        names.append(cells[0])
    return tuple(names)


def _pillar_anchor_map_from_table(section: str) -> dict[str, str]:
    anchors: dict[str, str] = {}
    for line in section.splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0] in {"Product name", "---"}:
            continue
        anchors[cells[0]] = cells[1]
    return anchors


def test_public_docs_do_not_overmap_runtime_details() -> None:
    # Given: public docs define the reduced Zeus core product-domain layer.
    readme = _read(PROJECT_ROOT / "README.md")
    public_text = "\n".join(_read(path) for path in PUBLIC_DOCS)
    core_language_section = _section(readme, "## Zeus Core Language")

    # When: the public docs are inspected as a static language contract.
    public_doc_names = _pillar_names_from_table(core_language_section)

    # Then: only the approved 12 names are canonical product-domain pillars.
    assert public_doc_names == APPROVED_CORE_NAMES
    for name in APPROVED_CORE_NAMES:
        assert name in public_text
    assert "technical runtime identifiers are preserved" in public_text
    assert "product-domain labels do not rename runtime modules" in public_text
    assert "Hermes remains upstream/reference only" in public_text
    assert "Mercury is the Zeus internal transport product name" in public_text

    # Then: public docs keep the v0.3.0 no-live boundary explicit.
    for claim in ACTIVE_LIVE_CLAIMS:
        assert claim not in public_text
    assert "designed/prepared/dry-run/future" in public_text

    # Then: unapproved mythology terms never appear as active pillars.
    for name in FORBIDDEN_MYTH_PILLARS:
        active_pattern = re.compile(rf"\|\s*{re.escape(name)}\s*\|")
        assert active_pattern.search(public_text) is None

    # Then: user-visible public evidence counts are consistent across badges and tables.
    for marker in STALE_PUBLIC_EVIDENCE_MARKERS:
        assert marker not in public_text
    for marker in CURRENT_PUBLIC_EVIDENCE_MARKERS:
        assert marker in public_text


def test_core_language_docs_match_runtime_anchor_contract() -> None:
    from zeus_agent.product_runtime.domain_language import core_domain_language_summary

    # Given: source runtime mapping and public docs both describe the approved core language.
    summary = core_domain_language_summary()
    runtime_anchors = {
        item.product_name: set(item.technical_anchors)
        for item in summary.mappings
    }
    public_text = "\n".join(_read(path) for path in PUBLIC_DOCS)
    readme_anchors = _pillar_anchor_map_from_table(
        _section(_read(PROJECT_ROOT / "README.md"), "## Zeus Core Language")
    )

    # Then: every approved term has docs/runtime anchor coverage.
    assert tuple(runtime_anchors) == APPROVED_CORE_NAMES
    assert tuple(readme_anchors) == APPROVED_CORE_NAMES
    for product_name, required_anchors in REQUIRED_RUNTIME_ANCHORS.items():
        for anchor in required_anchors:
            assert anchor in runtime_anchors[product_name], product_name
            assert anchor in public_text, (product_name, anchor)
            assert anchor in readme_anchors[product_name], (product_name, anchor)

    # Then: Poseidon stays gateway/surface containment language, not sandbox naming.
    poseidon_doc = next(
        line for line in public_text.splitlines() if line.startswith("| Poseidon |")
    )
    assert "gateway_runtime" in poseidon_doc
    assert "Sandbox, environment, and volatile" not in poseidon_doc


def test_public_master_plans_do_not_name_private_harness_as_existing_public_anchor() -> None:
    for path in PUBLIC_MASTER_PLAN_DOCS:
        text = _read(path)
        assert "| Evidence checkpoint | `harness/evidence/evidence.jsonl`" not in text
