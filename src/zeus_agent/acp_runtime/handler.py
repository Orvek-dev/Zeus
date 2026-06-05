from __future__ import annotations

from pydantic import JsonValue

from zeus_agent.objective_runtime import ObjectiveCompiler
from zeus_agent.security.credentials import redact_secret_spans

JsonObject = dict[str, JsonValue]


def handle_acp_message(message: JsonObject) -> JsonObject:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        return _response(
            request_id,
            {
                "name": "Zeus ACP",
                "version": "0.1.0",
                "write_authority": "blocked_by_default",
                "live_production_claimed": False,
            },
        )
    if method == "zeus.objective.compile":
        params = message.get("params")
        objective = ""
        if isinstance(params, dict) and isinstance(params.get("objective"), str):
            objective = params["objective"]
        contract = ObjectiveCompiler().compile(objective).model_dump(mode="json")
        contract["live_production_claimed"] = False
        return _response(request_id, contract)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32001, "message": "acp_method_blocked"},
        "result": {
            "handler_executed": False,
            "network_opened": False,
            "method": redact_secret_spans(str(method or "")),
            "live_production_claimed": False,
        },
    }


def _response(request_id: JsonValue, result: JsonObject) -> JsonObject:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}
