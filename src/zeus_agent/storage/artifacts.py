"""Artifact helpers for large tool outputs."""

from __future__ import annotations

from pathlib import Path

from zeus_agent.paths import ensure_private_dir
from zeus_agent.security.redaction import redact_text
from zeus_agent.storage.jsonio import write_private_json
from zeus_agent.storage.run_store import RunStore
from zeus_agent.storage.state import StateStore


DEFAULT_PREVIEW_CHARS = 20_000


def persist_large_text(
    run_id: str,
    name: str,
    text: str,
    *,
    home: Path | None = None,
    preview_chars: int = DEFAULT_PREVIEW_CHARS,
) -> tuple[str, str | None, bool, list[str]]:
    """Return redacted preview, optional artifact path, truncation flag, findings."""

    redacted = redact_text(text)
    value = redacted.value
    truncated = len(value) > preview_chars
    artifact_path: str | None = None
    if truncated:
        store = RunStore(home)
        path = store.artifacts_for(run_id).run_dir / "artifacts" / "tool_outputs" / f"{name}.txt"
        ensure_private_dir(path.parent)
        path.write_text(value, encoding="utf-8")
        try:
            path.chmod(0o600)
        except PermissionError:
            pass
        artifact_path = str(path)
        StateStore(home).record_artifact(
            run_id,
            artifact_path,
            "tool_output",
            {"name": name, "preview_chars": preview_chars, "original_chars": len(value)},
        )
        preview = (
            value[:preview_chars]
            + f"\n\n[Zeus stored full output at {artifact_path}; preview truncated.]"
        )
    else:
        preview = value
    return preview, artifact_path, truncated, list(redacted.findings)


def persist_json_artifact(
    run_id: str,
    artifact_type: str,
    filename: str,
    payload: dict[str, object],
    *,
    home: Path | None = None,
) -> Path:
    store = RunStore(home)
    path = store.artifacts_for(run_id).run_dir / "artifacts" / artifact_type / filename
    write_private_json(path, payload)
    StateStore(home).record_artifact(run_id, str(path), artifact_type, {"filename": filename})
    return path

