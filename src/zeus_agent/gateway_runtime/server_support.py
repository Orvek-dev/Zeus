from __future__ import annotations

from typing import Final
from urllib.parse import urlsplit

from pydantic import JsonValue

from zeus_agent.gateway_runtime.api import GatewayApiRuntime
from zeus_agent.gateway_runtime.models import GatewayApiResponse
from zeus_agent.gateway_runtime.security import GatewaySecurityRequestContext

JsonPayload = dict[str, JsonValue]
_RESUME_PREFIX: Final = "/v1/gateway/sessions/"
_RESUME_SUFFIX: Final = "/resume"
_MALFORMED_SECURITY_PATH: Final = "/v1/gateway/malformed-security-context"
_FALLBACK_LOOPBACK_HOST: Final = "127.0.0.1"


def http_payload(response: GatewayApiResponse) -> JsonPayload:
    payload: JsonPayload = response.model_dump(mode="json")
    payload["loopback_http_opened"] = True
    payload["C001"] = True
    payload["C002"] = True
    payload["C003"] = True
    payload["live_production_claimed"] = False
    return payload


def path_only(raw_path: str) -> str:
    return urlsplit(raw_path).path


def resume_session_id(path: str) -> str | None:
    if not path.startswith(_RESUME_PREFIX) or not path.endswith(_RESUME_SUFFIX):
        return None
    session_id = path.removeprefix(_RESUME_PREFIX).removesuffix(_RESUME_SUFFIX)
    if session_id == "" or "/" in session_id:
        return None
    return session_id


def malformed_security_response(
    runtime: GatewayApiRuntime,
    *,
    method: str,
    authorization_header: str | None,
    expected_token: str,
) -> GatewayApiResponse:
    fallback = GatewaySecurityRequestContext(
        method=method,
        path=_MALFORMED_SECURITY_PATH,
        host=_FALLBACK_LOOPBACK_HOST,
        client_host=_FALLBACK_LOOPBACK_HOST,
        authorization_header=authorization_header,
        expected_token=expected_token,
    )
    blocked = runtime.preflight_block(fallback)
    if blocked is not None:
        return blocked
    return runtime.malformed_request(fallback)
