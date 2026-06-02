from __future__ import annotations

from typing import Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_call_id: str
    capability_id: str
    arguments: dict[str, str] = Field(default_factory=dict)


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt_context: Dict[str, Union[str, List[str]]]
    tool_schema: List[Dict[str, object]]


class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_id: str
    content: str
    tool_call: Optional[ToolCall] = None


class ModelCapabilityMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str
    model_id: str
    tool_calling: bool
    json_mode: bool
    streaming: bool
    local_private: bool
    context_length: int
    fallback_eligible: bool


class FakeModelRuntime:
    def __init__(
        self,
        matrix: ModelCapabilityMatrix,
        responses: list[ModelResponse],
    ) -> None:
        self.matrix = matrix
        self._responses = list(responses)
        self._index = 0

    def next_response(self, request: ModelRequest) -> ModelResponse:
        if request.tool_schema and not self.matrix.tool_calling:
            return ModelResponse(turn_id="turn-plan-only", content="tool schema unsupported")
        if self._index >= len(self._responses):
            return ModelResponse(turn_id="turn-empty", content="no more scripted responses")
        response = self._responses[self._index]
        self._index += 1
        return response


def fake_tool_matrix() -> ModelCapabilityMatrix:
    return ModelCapabilityMatrix(
        provider_id="fake-local",
        model_id="fake-tool-model",
        tool_calling=True,
        json_mode=True,
        streaming=False,
        local_private=True,
        context_length=8192,
        fallback_eligible=True,
    )
