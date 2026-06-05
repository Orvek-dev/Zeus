from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue

LiveSealedCredentialDecision = Literal["released", "blocked"]

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


@dataclass(frozen=True)
class LiveSealedCredential:
    header_name: str
    header_value_ref: str
    _header_value: str = field(repr=False)

    def reveal_for_transport(self) -> str:
        return self._header_value

    def to_payload(self) -> dict[str, str]:
        return {
            "header_name": self.header_name,
            "header_value_ref": self.header_value_ref,
        }


class LiveSealedCredentialReceipt(BaseModel):
    model_config = _MODEL_CONFIG

    consumer_ref: str
    credential_value_received: bool
    header_name_seen: str
    header_value_ref_seen: str
    material_released: bool = False
    raw_secret_returned: bool = False
    no_secret_echo: bool = True


class LiveSealedCredentialConsumer(Protocol):
    def consume(self, credential: LiveSealedCredential) -> LiveSealedCredentialReceipt:
        ...


class StaticSealedCredentialConsumer:
    def __init__(self, consumer_ref: str) -> None:
        self.consumer_ref = consumer_ref

    def consume(self, credential: LiveSealedCredential) -> LiveSealedCredentialReceipt:
        return LiveSealedCredentialReceipt(
            consumer_ref=self.consumer_ref,
            credential_value_received=credential.reveal_for_transport() != "",
            header_name_seen=credential.header_name,
            header_value_ref_seen=credential.header_value_ref,
        )


class LiveSealedCredentialReleaseResult(BaseModel):
    model_config = _MODEL_CONFIG

    decision: LiveSealedCredentialDecision
    release_id: Optional[str]
    injection_id: Optional[str]
    material_proof_id: Optional[str]
    consumer_ref: Optional[str]
    release_ref: Optional[str]
    header_name: Optional[str]
    header_value_ref: Optional[str]
    blocked_reasons: tuple[str, ...] = ()
    credential_injection_bound: bool = False
    secret_material_bound: bool = False
    consumer_bound: bool = False
    sealed_credential_released: bool = False
    material_released_to_consumer: bool = False
    credential_material_accessed: bool = False
    material_released: bool = False
    raw_secret_returned: bool = False
    network_opened: bool = False
    non_loopback_network_opened: bool = False
    handler_executed: bool = False
    external_delivery_opened: bool = False
    live_transport_enabled: bool = False
    execution_allowed: bool = False
    authority_granted: bool = False
    server_started: bool = False
    resources_enabled: bool = False
    prompts_enabled: bool = False
    no_secret_echo: bool = True
    live_production_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")
