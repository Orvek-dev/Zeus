from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PluginDecision = Literal["quarantined", "blocked"]


class PluginManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    plugin_id: str
    name: str
    version: str
    entrypoint: str
    permissions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    sha256: str


class PluginValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    decision: PluginDecision
    reason: str
    manifest: Optional[PluginManifest] = None
    blocked_reasons: tuple[str, ...] = Field(default_factory=tuple)
    tool_registration_allowed: bool = False
    handler_executed: bool = False
    network_opened: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False
