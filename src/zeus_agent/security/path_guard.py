"""Path policy helpers.

These helpers are intentionally small for the first milestone. The execution
sandbox is not implemented yet, so this module focuses on preventing accidental
state writes outside declared local roots.
"""

from __future__ import annotations

from pathlib import Path


class PathPolicyError(ValueError):
    """Raised when a path falls outside the allowed local policy."""


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def assert_path_under_roots(path: Path, roots: list[Path]) -> Path:
    resolved = path.expanduser().resolve()
    resolved_roots = [root.expanduser().resolve() for root in roots]
    if any(_is_relative_to(resolved, root) for root in resolved_roots):
        return resolved
    allowed = ", ".join(str(root) for root in resolved_roots)
    raise PathPolicyError(f"path is outside allowed roots: {resolved}; allowed={allowed}")
