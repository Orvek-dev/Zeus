"""Shared SSRF-safe URL guard (M3 / C3).

One reusable gate for every outbound fetch (provider, MCP, research): scheme
allowlist, host allowlist, and deny-by-default for internal/metadata hosts when
no allowlist constrains the target. Fixes the two MEDIUM SSRF findings in one
place instead of per-runtime.
"""

from __future__ import annotations

from .guard import (
    SafeUrlError,
    assert_safe_url,
    is_internal_host,
    url_violation,
)

__all__ = [
    "SafeUrlError",
    "assert_safe_url",
    "is_internal_host",
    "url_violation",
]
