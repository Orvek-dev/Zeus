from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from zeus_agent.security.credentials import redact_secret_like

DraftStatus = Literal["drafted"]


@dataclass(frozen=True)
class GatewayDraft:
    command: str
    target: str
    draft_only: bool
    side_effects: bool
    status: DraftStatus


@dataclass(frozen=True)
class CronDraft:
    command: str
    target: str
    draft_only: bool
    side_effects: bool
    status: DraftStatus


def draft_gateway_command(*, command: str, target: str) -> GatewayDraft:
    return GatewayDraft(
        command=redact_secret_like(command),
        target=redact_secret_like(target),
        draft_only=True,
        side_effects=False,
        status="drafted",
    )


def draft_cron_command(*, command: str, target: str) -> CronDraft:
    return CronDraft(
        command=redact_secret_like(command),
        target=redact_secret_like(target),
        draft_only=True,
        side_effects=False,
        status="drafted",
    )
