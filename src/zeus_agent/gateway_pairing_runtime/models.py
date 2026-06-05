from __future__ import annotations

from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, JsonValue

MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class GatewayPairingProofResult(BaseModel):
    model_config = MODEL_CONFIG

    decision: str
    pairing: Optional[dict[str, JsonValue]] = None
    blocked_reasons: tuple[str, ...] = ()
    redacted_input: Optional[str] = None
    pairing_configured: bool = False
    proof_material_accessed: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class GatewayPairingListResult(BaseModel):
    model_config = MODEL_CONFIG

    decision: str
    paired_target_count: int
    pairings: tuple[dict[str, JsonValue], ...]
    config_path: str
    proof_material_accessed: bool = False
    credential_material_accessed: bool = False
    network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
