from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import JsonValue

from zeus_agent.trust_loop_runtime import SQLiteApprovalQueue, SQLiteControlPlaneStore

from .cards import pending_card


class WebhookDeliveryError(RuntimeError):
    def __init__(self, *, webhook_url: str, detail: str) -> None:
        self.webhook_url = webhook_url
        self.detail = detail
        super().__init__("webhook delivery failed for {0}: {1}".format(webhook_url, detail))


@dataclass(frozen=True, slots=True)
class WebhookDeliveryResult:
    pending: int
    delivered: int
    webhook_url: str
    status_code: int

    def to_payload(self) -> dict[str, JsonValue]:
        return {
            "pending": self.pending,
            "delivered": self.delivered,
            "webhook": self.webhook_url,
            "status_code": self.status_code,
        }


def deliver_pending_to_webhook(
    *,
    state_path: Path,
    webhook_url: str,
    timeout_seconds: float = 5.0,
) -> WebhookDeliveryResult:
    queue = SQLiteApprovalQueue(SQLiteControlPlaneStore(state_path))
    rows = queue.pending(now=datetime.now(timezone.utc))
    cards = [pending_card(parked) for parked in rows]
    payload = json.dumps({"cards": cards}, ensure_ascii=False, default=str).encode("utf-8")
    request = Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status_code = int(response.status)
    except HTTPError as exc:
        raise WebhookDeliveryError(
            webhook_url=webhook_url,
            detail="HTTP {0}".format(exc.code),
        ) from exc
    except URLError as exc:
        raise WebhookDeliveryError(
            webhook_url=webhook_url,
            detail=str(exc.reason),
        ) from exc
    return WebhookDeliveryResult(
        pending=len(cards),
        delivered=len(cards),
        webhook_url=webhook_url,
        status_code=status_code,
    )
