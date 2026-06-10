from __future__ import annotations

import ipaddress
from typing import Final, Optional
from urllib.parse import urlparse

_ALLOWED_SCHEMES: Final = frozenset({"http", "https"})
_LOOPBACK_HOSTS: Final = frozenset({"127.0.0.1", "localhost", "::1"})


class SafeUrlError(ValueError):
    """An outbound URL failed the SSRF guard."""


def is_internal_host(hostname: str) -> bool:
    """True for loopback, private, link-local, or cloud-metadata hosts."""
    host = hostname.strip().lower()
    if host in _LOOPBACK_HOSTS:
        return True
    if host == "metadata" or host.endswith(".internal") or host.endswith(".local"):
        return True
    if host == "169.254.169.254":  # cloud metadata
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


def url_violation(
    url: str,
    *,
    allowed_hosts: tuple[str, ...] = (),
    allow_loopback: bool = False,
) -> Optional[str]:
    """Return a violation reason, or None if the URL is safe to fetch.

    - scheme must be http/https
    - https required unless ``allow_loopback`` and the host is loopback
    - if an allowlist is given, the host must be in it
    - with no allowlist, internal/metadata hosts are denied (loopback only when
      ``allow_loopback`` is set)
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return "scheme_not_allowed"
    host = parsed.hostname
    if host is None or host == "":
        return "no_host"
    loopback = host.lower() in _LOOPBACK_HOSTS
    if parsed.scheme == "http" and not (allow_loopback and loopback):
        return "http_requires_loopback"
    # Internal/metadata hosts are blocked even if allowlisted — an allowlist is
    # not a license to reach the metadata service. Loopback needs an explicit opt-in.
    if is_internal_host(host) and not (allow_loopback and loopback):
        return "internal_host_blocked"
    if allowed_hosts and host not in allowed_hosts:
        return "host_not_allowlisted"
    return None


def assert_safe_url(
    url: str,
    *,
    allowed_hosts: tuple[str, ...] = (),
    allow_loopback: bool = False,
) -> None:
    reason = url_violation(url, allowed_hosts=allowed_hosts, allow_loopback=allow_loopback)
    if reason is not None:
        raise SafeUrlError(reason)
