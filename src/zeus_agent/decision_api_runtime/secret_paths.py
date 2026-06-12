from __future__ import annotations

from pathlib import PurePosixPath
from typing import Final

_SECRET_REASON: Final = "sensitive_path_read"
_SECRET_DIR_SEGMENTS: Final = frozenset(
    {".aws", ".azure", ".config/gcloud", ".gnupg", ".kube", ".ssh", "secrets"}
)
_EXACT_SECRET_NAMES: Final = frozenset(
    {
        ".env",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "credentials",
        "credentials.json",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "secrets.json",
    }
)
_ENV_EXAMPLE_NAMES: Final = frozenset(
    {
        ".env.example",
        ".env.sample",
        ".env.template",
        "example.env",
        "sample.env",
        "template.env",
    }
)
_SECRET_SUFFIXES: Final = (".key", ".p12", ".pem", ".pfx")


def secret_path_read_reason(path: str | None) -> str | None:
    if path is None:
        return None
    normalized = path.strip().replace("\\", "/")
    if not normalized:
        return None
    parts = tuple(part.lower() for part in PurePosixPath(normalized).parts if part not in {"/", ""})
    if not parts:
        return None
    basename = parts[-1]
    if basename in _ENV_EXAMPLE_NAMES:
        return None
    if basename in _EXACT_SECRET_NAMES or _is_env_file(basename):
        return _SECRET_REASON
    if any(basename.endswith(suffix) for suffix in _SECRET_SUFFIXES):
        return _SECRET_REASON
    if _has_secret_segment(parts):
        return _SECRET_REASON
    return None


def _is_env_file(basename: str) -> bool:
    return basename.endswith(".env") or basename.startswith(".env.")


def _has_secret_segment(parts: tuple[str, ...]) -> bool:
    joined = "/".join(parts)
    if ".config/gcloud" in joined:
        return True
    return any(part in _SECRET_DIR_SEGMENTS for part in parts)
