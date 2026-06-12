from __future__ import annotations

from pathlib import Path
from typing import Final


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
HARD_CLOSE_DOC: Final[Path] = PROJECT_ROOT / "docs/zeus-w205-w212-hard-close.md"
LIVE_OPT_IN_DOC: Final[Path] = PROJECT_ROOT / "docs/zeus-hermes-live-opt-in-boundary.md"
PUBLIC_PRIVATE_DOC: Final[Path] = PROJECT_ROOT / "docs/zeus-public-private-boundary.md"


def test_public_hard_close_doc_records_w205_through_w212() -> None:
    text = HARD_CLOSE_DOC.read_text(encoding="utf-8")

    for wave in range(205, 213):
        assert f"W{wave}" in text, f"missing W{wave} public hard-close note"

    assert "production live surface evidence" in text
    assert "project-mode release gate" in text
    assert "git-backed public release publication" in text


def test_public_boundary_docs_preserve_live_and_private_boundaries() -> None:
    live_text = LIVE_OPT_IN_DOC.read_text(encoding="utf-8")
    private_text = PUBLIC_PRIVATE_DOC.read_text(encoding="utf-8")

    assert "production live readiness remains blocked" in live_text
    assert "project-mode release gate" in live_text
    assert "docs/ai/" in private_text
    assert "harness/" in private_text
    assert "evidence/" in private_text
