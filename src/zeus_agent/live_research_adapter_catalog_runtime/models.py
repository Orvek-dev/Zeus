from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

AdapterState = Literal["owned_client"]
_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True, strict=True)


class LiveResearchAdapterSpec(BaseModel):
    model_config = _MODEL_CONFIG

    adapter_id: str
    display_name: str
    source_id: str
    state: AdapterState = "owned_client"
    transport_runtime: str = "live_research_owned_client_transport"
    client_module: str
    default_endpoint: Optional[str] = None
    endpoint_config_required: bool = False
    credential_scope: Optional[str] = None
    activation_policy_required: bool = True
    approval_required: bool = True
    source_pin_required: bool = True
    owned_client_supported: bool = True
    real_fetcher_available: bool = True
    production_fetcher_configured: bool = False
    network_opened: bool = False
    live_production_claimed: bool = False
