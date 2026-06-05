from __future__ import annotations

from typing import Final, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class WebResearchHttpRequest(BaseModel):
    model_config = _MODEL_CONFIG

    url: str
    timeout_ms: int

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class WebResearchHttpResponse(BaseModel):
    model_config = _MODEL_CONFIG

    status_code: int
    latency_ms: int
    payload: dict[str, JsonValue]


class WebResearchHttpFetcher(Protocol):
    def fetch(self, request: WebResearchHttpRequest) -> WebResearchHttpResponse:
        ...


class StaticWebResearchHttpFetcher:
    def __init__(self, response: WebResearchHttpResponse) -> None:
        self.response = response
        self.requests: list[WebResearchHttpRequest] = []

    def fetch(self, request: WebResearchHttpRequest) -> WebResearchHttpResponse:
        self.requests.append(request)
        return self.response
