from __future__ import annotations

from typing import Final, Protocol

from pydantic import BaseModel, ConfigDict, JsonValue

_MODEL_CONFIG: Final = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class CommunityResearchHttpRequest(BaseModel):
    model_config = _MODEL_CONFIG

    url: str
    timeout_ms: int

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


class CommunityResearchHttpResponse(BaseModel):
    model_config = _MODEL_CONFIG

    status_code: int
    latency_ms: int
    payload: dict[str, JsonValue]


class CommunityResearchHttpFetcher(Protocol):
    def fetch(self, request: CommunityResearchHttpRequest) -> CommunityResearchHttpResponse:
        ...


class StaticCommunityResearchHttpFetcher:
    def __init__(self, response: CommunityResearchHttpResponse) -> None:
        self.response = response
        self.requests: list[CommunityResearchHttpRequest] = []

    def fetch(self, request: CommunityResearchHttpRequest) -> CommunityResearchHttpResponse:
        self.requests.append(request)
        return self.response
