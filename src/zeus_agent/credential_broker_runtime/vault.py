from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Final, Optional, Protocol

_ENV_PREFIX: Final = "ZEUS_SECRET_"
_SCOPE_TO_ENV: Final = re.compile(r"[._-]")


@dataclass(frozen=True)
class VaultEntry:
    """Resolved secret material plus the header it travels in.

    The raw value is kept out of ``repr`` so a logged entry never echoes the
    secret; only the broker's sealed-release path may reveal it.
    """

    header_name: str
    _value: str = field(repr=False)

    def reveal(self) -> str:
        return self._value


class CredentialVault(Protocol):
    def resolve(self, scope_label: str) -> Optional[VaultEntry]:
        ...


class EnvCredentialVault:
    """Vault backend over process environment variables.

    Scope ``external.github.readonly`` resolves from
    ``ZEUS_SECRET_EXTERNAL_GITHUB_READONLY``. This is the local-first default;
    a real secret manager can implement the same protocol later.
    """

    def __init__(self, *, header_name: str = "Authorization") -> None:
        self._header_name = header_name

    def resolve(self, scope_label: str) -> Optional[VaultEntry]:
        env_name = _ENV_PREFIX + _SCOPE_TO_ENV.sub("_", scope_label.strip()).upper()
        value = os.environ.get(env_name, "")
        if value == "":
            return None
        return VaultEntry(header_name=self._header_name, _value=value)


class InMemoryCredentialVault:
    """Deterministic vault for tests and loopback conformance scenarios."""

    def __init__(self) -> None:
        self._entries: dict[str, VaultEntry] = {}

    def put(self, scope_label: str, value: str, *, header_name: str = "Authorization") -> None:
        self._entries[scope_label.strip()] = VaultEntry(header_name=header_name, _value=value)

    def resolve(self, scope_label: str) -> Optional[VaultEntry]:
        return self._entries.get(scope_label.strip())
