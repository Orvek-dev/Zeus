from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, Optional, Sequence

from pydantic import BaseModel, ConfigDict

from zeus_agent.model_runtime.fake import ModelCapabilityMatrix, fake_tool_matrix

ProviderKind = Literal["fake", "local", "external"]
RouteDecision = Literal["selected", "blocked"]

_SECRET_PREFIX: Final = "sk-"


class ProviderRouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderKind
    required_tool_calling: bool = False
    required_json_mode: bool = False
    required_streaming: bool = False
    local_private: Optional[bool] = None
    credential_scope: Optional[str] = None
    network_allowed: bool = False


class ProviderRouteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: RouteDecision
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    reason: Optional[str] = None
    local_private: Optional[bool] = None
    tool_calling: Optional[bool] = None
    json_mode: Optional[bool] = None
    streaming: Optional[bool] = None


@dataclass(frozen=True)
class ProviderDeclaration:
    provider: ProviderKind
    matrix: ModelCapabilityMatrix


class ProviderRouter:
    def __init__(self, declarations: Sequence[ProviderDeclaration]) -> None:
        self._declarations = tuple(declarations)

    def route(self, request: ProviderRouteRequest) -> ProviderRouteResult:
        blocked_reason = _external_block_reason(request)
        if blocked_reason is not None:
            return _blocked_result(blocked_reason, request.local_private)

        for declaration in self._declarations:
            if declaration.provider == request.provider and _matches(
                declaration.matrix,
                request,
            ):
                return _selected_result(declaration.matrix)

        return _blocked_result("no_compatible_provider", request.local_private)


def default_provider_router() -> ProviderRouter:
    return ProviderRouter(
        [
            ProviderDeclaration(provider="fake", matrix=fake_tool_matrix()),
            ProviderDeclaration(provider="local", matrix=_local_matrix()),
            ProviderDeclaration(provider="external", matrix=_external_matrix()),
        ],
    )


def _local_matrix() -> ModelCapabilityMatrix:
    return ModelCapabilityMatrix(
        provider_id="local-private",
        model_id="local-private-stub",
        tool_calling=True,
        json_mode=True,
        streaming=True,
        local_private=True,
        context_length=32768,
        fallback_eligible=False,
    )


def _external_matrix() -> ModelCapabilityMatrix:
    return ModelCapabilityMatrix(
        provider_id="external",
        model_id="external-stub",
        tool_calling=True,
        json_mode=True,
        streaming=True,
        local_private=False,
        context_length=128000,
        fallback_eligible=False,
    )


def _external_block_reason(request: ProviderRouteRequest) -> Optional[str]:
    if request.provider != "external":
        return None
    if not request.network_allowed:
        return "network_not_allowed"
    if request.credential_scope is None or request.credential_scope.strip() == "":
        return "missing_credential_scope"
    if _is_secret_like(request.credential_scope):
        return "secret_like_credential_scope"
    return None


def _is_secret_like(value: str) -> bool:
    return value.strip().lower().startswith(_SECRET_PREFIX)


def _matches(
    matrix: ModelCapabilityMatrix,
    request: ProviderRouteRequest,
) -> bool:
    if request.local_private is not None and matrix.local_private != request.local_private:
        return False
    if request.required_tool_calling and not matrix.tool_calling:
        return False
    if request.required_json_mode and not matrix.json_mode:
        return False
    return not (request.required_streaming and not matrix.streaming)


def _selected_result(matrix: ModelCapabilityMatrix) -> ProviderRouteResult:
    return ProviderRouteResult(
        decision="selected",
        provider_id=matrix.provider_id,
        model_id=matrix.model_id,
        local_private=matrix.local_private,
        tool_calling=matrix.tool_calling,
        json_mode=matrix.json_mode,
        streaming=matrix.streaming,
    )


def _blocked_result(
    reason: str,
    requested_local_private: Optional[bool],
) -> ProviderRouteResult:
    return ProviderRouteResult(
        decision="blocked",
        reason=reason,
        local_private=requested_local_private,
    )
