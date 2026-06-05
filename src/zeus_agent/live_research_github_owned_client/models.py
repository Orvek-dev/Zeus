from __future__ import annotations

from typing import Final, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class ResearchHttpRequest(BaseModel):
    model_config = _MODEL_CONFIG

    url: str
    timeout_ms: int

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class ResearchHttpResponse(BaseModel):
    model_config = _MODEL_CONFIG

    status_code: int
    latency_ms: int
    payload: dict[str, JsonValue]


class ResearchHttpFetcher(Protocol):
    def fetch(self, request: ResearchHttpRequest) -> ResearchHttpResponse:
        ...


class StaticResearchHttpFetcher:
    def __init__(self, response: ResearchHttpResponse) -> None:
        self.response = response
        self.requests: list[ResearchHttpRequest] = []

    def fetch(self, request: ResearchHttpRequest) -> ResearchHttpResponse:
        self.requests.append(request)
        return self.response
