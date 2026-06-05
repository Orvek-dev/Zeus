from __future__ import annotations

from datetime import datetime, timezone
from typing import Final

TARGET_VERSION: Final = "v1.0.0-rc.7"
OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.0.0-rc.7.provider_live_optin"
NOW: Final = datetime(2026, 6, 6, 2, 0, tzinfo=timezone.utc)
EXPIRES_AT: Final = datetime(2026, 6, 7, 2, 0, tzinfo=timezone.utc)
DEFAULT_ENDPOINT: Final = "https://api.openai.local/v1/chat/completions"
DEFAULT_ALLOWED_HOST: Final = "api.openai.local"
DEFAULT_SECRET_REF: Final = "env://ZEUS_RC7_PROVIDER_KEY"
DEFAULT_MODEL: Final = "gpt-rc7-external"
DEFAULT_MESSAGE: Final = "summarize provider live opt-in checkpoint"
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
)
