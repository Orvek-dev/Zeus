from __future__ import annotations

import json
from typing import Optional

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise ValueError("{0}_empty".format(field_name))
    return normalized


class AcsInterception(BaseModel):
    """One interception point from an external ACS-style manifest, mapped to a
    Zeus capability id."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    point: str
    capability_id: str
    description: Optional[str] = None

    @field_validator("point", "capability_id")
    @classmethod
    def validate_text(cls, value: str, info: ValidationInfo) -> str:
        return require_text(value, info.field_name)


class AcsManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    name: str
    version: str = "0"
    interceptions: tuple[AcsInterception, ...] = ()


def load_acs_manifest(text: str) -> AcsManifest:
    """Read-compat loader for ACS-style manifests (ride the spec, don't fight it).

    Accepts JSON directly; YAML works when PyYAML happens to be installed —
    the spec is YAML-first, but Zeus does not take a YAML dependency for a
    compatibility shim. Tolerates the field-name variants seen in the wild
    (``interception_points``/``interceptions``, ``capability``/``maps_to``).
    """
    data = _parse(text)
    if not isinstance(data, dict):
        raise ValueError("acs_manifest_not_a_mapping")
    raw_points = data.get("interceptions", data.get("interception_points", []))
    interceptions: list[AcsInterception] = []
    if isinstance(raw_points, list):
        for item in raw_points:
            if not isinstance(item, dict):
                continue
            point = item.get("point", item.get("name", item.get("id")))
            capability = item.get(
                "capability_id", item.get("capability", item.get("maps_to"))
            )
            if not isinstance(point, str) or not isinstance(capability, str):
                continue
            description = item.get("description")
            interceptions.append(
                AcsInterception(
                    point=point,
                    capability_id=capability,
                    description=description if isinstance(description, str) else None,
                )
            )
    return AcsManifest(
        name=str(data.get("name", "unnamed-acs-manifest")),
        version=str(data.get("version", "0")),
        interceptions=tuple(interceptions),
    )


def capability_map(manifest: AcsManifest) -> dict[str, str]:
    """interception point → Zeus capability_id, for gate adapters."""
    return {item.point: item.capability_id for item in manifest.interceptions}


def _parse(text: str):
    try:
        return json.loads(text)
    except ValueError:
        pass
    try:  # optional YAML path; absence is fine
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ValueError("acs_manifest_unparseable_install_pyyaml_for_yaml") from exc
    return yaml.safe_load(text)
