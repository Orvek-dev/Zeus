from __future__ import annotations

from typing import Optional

from zeus_agent.live_sealed_credential_runtime import (
    LiveSealedCredential,
    LiveSealedCredentialReceipt,
)


class CredentialCapture:
    def __init__(self, consumer_ref: str) -> None:
        self.consumer_ref = consumer_ref
        self.header_name: Optional[str] = None
        self.header_value_ref: Optional[str] = None
        self.header_value: Optional[str] = None

    def consume(self, credential: LiveSealedCredential) -> LiveSealedCredentialReceipt:
        self.header_name = credential.header_name
        self.header_value_ref = credential.header_value_ref
        self.header_value = credential.reveal_for_transport()
        return LiveSealedCredentialReceipt(
            consumer_ref=self.consumer_ref,
            credential_value_received=self.header_value != "",
            header_name_seen=credential.header_name,
            header_value_ref_seen=credential.header_value_ref,
        )
