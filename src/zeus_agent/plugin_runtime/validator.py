from __future__ import annotations

import re
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.security.credentials import redact_secret_spans

from .models import PluginManifest, PluginValidationResult

JsonObject = dict[str, JsonValue]
_ID_PATTERN: Final = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_SEMVER_PATTERN: Final = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$")
_SHA256_PATTERN: Final = re.compile(r"^[a-f0-9]{64}$")
_ALLOWED_PERMISSIONS: Final = frozenset(
    {
        "tool.register",
        "tool.read",
        "memory.read",
        "wiki.read",
        "session.read",
    },
)
_ALLOWED_DEPENDENCIES: Final = frozenset({"pydantic", "rich", "typer"})


def validate_plugin_manifest(raw: JsonValue) -> PluginValidationResult:
    if not isinstance(raw, dict):
        return _blocked(("malformed_manifest",), None)

    manifest = PluginManifest(
        plugin_id=_text(raw.get("plugin_id"), "plugin_id"),
        name=_text(raw.get("name"), "name"),
        version=_text(raw.get("version"), "version"),
        entrypoint=_text(raw.get("entrypoint"), "entrypoint"),
        permissions=_text_tuple(raw.get("permissions")),
        dependencies=_text_tuple(raw.get("dependencies")),
        sha256=_text(raw.get("sha256"), "sha256"),
    )
    reasons = _blocked_reasons(manifest)
    if reasons:
        return _blocked(reasons, manifest)
    return PluginValidationResult(
        decision="quarantined",
        reason="plugin_candidate_quarantined",
        manifest=manifest,
        blocked_reasons=(),
        tool_registration_allowed=False,
        handler_executed=False,
        network_opened=False,
        no_secret_echo=True,
        live_production_claimed=False,
    )


def _blocked(reasons: tuple[str, ...], manifest: Optional[PluginManifest]) -> PluginValidationResult:
    return PluginValidationResult(
        decision="blocked",
        reason="plugin_manifest_blocked",
        manifest=manifest,
        blocked_reasons=reasons,
        tool_registration_allowed=False,
        handler_executed=False,
        network_opened=False,
        no_secret_echo=True,
        live_production_claimed=False,
    )


def _blocked_reasons(manifest: PluginManifest) -> tuple[str, ...]:
    reasons: list[str] = []
    if _ID_PATTERN.fullmatch(manifest.plugin_id) is None:
        reasons.append("malformed_plugin_id")
    if _SEMVER_PATTERN.fullmatch(manifest.version) is None:
        reasons.append("invalid_version")
    if _SHA256_PATTERN.fullmatch(manifest.sha256) is None:
        reasons.append("invalid_sha256")
    if manifest.entrypoint.startswith("/") or ".." in manifest.entrypoint or not manifest.entrypoint.startswith("plugins/"):
        reasons.append("unsafe_entrypoint")
    if any(permission not in _ALLOWED_PERMISSIONS for permission in manifest.permissions):
        reasons.append("unsafe_permission")
    if any(dependency not in _ALLOWED_DEPENDENCIES for dependency in manifest.dependencies):
        reasons.append("untrusted_dependency")
    return tuple(dict.fromkeys(reasons))


def _text(value: JsonValue | None, field_name: str) -> str:
    if not isinstance(value, str):
        return ""
    redacted = redact_secret_spans(value)
    return redacted.strip()


def _text_tuple(value: JsonValue | None) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(redact_secret_spans(item).strip() for item in value if isinstance(item, str) and item.strip())
