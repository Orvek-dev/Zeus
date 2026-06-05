from __future__ import annotations

from datetime import datetime, timezone
from typing import Final

TARGET_VERSION: Final = "v1.0.0-rc.8"
OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.0.0-rc.8.provider_owned_client_live"
NOW: Final = datetime(2026, 6, 6, 4, 0, tzinfo=timezone.utc)
EXPIRES_AT: Final = datetime(2026, 6, 7, 4, 0, tzinfo=timezone.utc)
DEFAULT_ENDPOINT: Final = "https://api.openai.local/v1/chat/completions"
DEFAULT_ALLOWED_HOST: Final = "api.openai.local"
DEFAULT_SECRET_REF: Final = "env://ZEUS_RC8_PROVIDER_KEY"
DEFAULT_MODEL: Final = "gpt-rc8-owned-client"
DEFAULT_MESSAGE: Final = "summarize provider owned client live checkpoint"
PROVIDER_RISKS: Final[tuple[str, ...]] = (
    "network",
    "credential_material_access",
    "external_provider_inference",
)
PROVIDER_LIVE_RISKS: Final[tuple[str, ...]] = (
    "network",
    "credential_material_access",
    "external_provider_inference",
    "live_transport",
    "owned_client_adapter",
)
