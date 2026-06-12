"""Public-docs contract: the README family must describe the CONTROL PLANE.

The pre-refoundation product language (the 12-pillar mythology table, wave-era
test-count snapshots, agent-platform live claims) must never reappear on the
public entry points, and the EN/KO entry docs must stay in sync on the facts
that gate trust: version, evidence counts, the four gates, the receipt
contract, and the honest alpha boundary.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
README_EN: Final[Path] = PROJECT_ROOT / "README.md"
README_KO: Final[Path] = PROJECT_ROOT / "README.ko.md"
CONNECTING: Final[Path] = PROJECT_ROOT / "CONNECTING.md"
SECURITY: Final[Path] = PROJECT_ROOT / "SECURITY.md"

PUBLIC_MASTER_PLAN_DOCS: Final[tuple[Path, ...]] = (
    PROJECT_ROOT / "docs/hermes-grade-platform-master-design.md",
    PROJECT_ROOT / "docs/hermes-live-platform-absorption-master-plan.md",
)

# Pre-refoundation language that must stay off the public entry points.
LEGACY_PILLARS: Final[tuple[str, ...]] = (
    "Athena",
    "Thunderbolt",
    "Aegis",
    "Apollo",
    "Hephaestus",
    "Poseidon",
    "Artemis",
    "Demeter",
    "Olympus",
    "Prometheus",
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
STALE_EVIDENCE_MARKERS: Final[tuple[str, ...]] = (
    "tests-1791",
    "`1791` public tests passed",
    "tests-1927",
    "`1927`",
    "12%2F12%20starter",
    "`12/12` governed scenarios",
    "zeus dev",
    "docs/commands.md",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readmes_carry_current_control_plane_facts() -> None:
    en = _read(README_EN)
    ko = _read(README_KO)

    for text, name in ((en, "EN"), (ko, "KO")):
        # version + evidence badges stay in sync with the package reality
        assert "version-1.0.0--alpha.6" in text, name
        assert "tests-291%20passed" in text, name
        assert "conformance-102%20tests" in text, name
        assert "`291`" in text, name
        assert "`102`" in text, name
        for marker in STALE_EVIDENCE_MARKERS:
            assert marker not in text, (name, marker)

    # the four gates and the receipt contract are the headline, both languages
    assert "## The Four Gates" in en
    assert "final-action receipt contract" in en.lower()
    assert "Honest boundary" in en
    assert "## 네 개의 관문" in ko
    assert "최종 행동-영수증 계약" in ko
    assert "정직한 경계" in ko

    # entry docs cross-link: host onboarding, security posture, the other language
    assert "CONNECTING.md" in en and "SECURITY.md" in en and "README.ko.md" in en
    assert "CONNECTING" in ko and "SECURITY.md" in ko and "README.md" in ko


def test_legacy_platform_language_stays_off_public_entry_points() -> None:
    for path in (README_EN, README_KO, CONNECTING, SECURITY):
        text = _read(path)
        assert "## Zeus Core Language" not in text, path
        for claim in ACTIVE_LIVE_CLAIMS:
            assert claim not in text, (path, claim)
        # mythology pillars must not appear as canonical product table rows
        for name in LEGACY_PILLARS:
            active_pattern = re.compile(rf"\|\s*{re.escape(name)}\s*\|")
            assert active_pattern.search(text) is None, (path, name)


def test_connecting_and_security_keep_their_anchors() -> None:
    connecting = _read(CONNECTING)
    assert "never zero-confirm" in connecting
    assert "zeus pair --approve" in connecting

    security = _read(SECURITY)
    assert "v1.0.0-alpha Boundary" in security
    assert "v5.0.0" not in security  # the stale boundary heading stays dead


def test_archived_docs_are_labelled_and_keep_private_anchors_out() -> None:
    for path in PUBLIC_MASTER_PLAN_DOCS:
        text = _read(path)
        assert "ARCHIVED" in text, path  # pre-refoundation records say so up front
        assert "| Evidence checkpoint | `harness/evidence/evidence.jsonl`" not in text
