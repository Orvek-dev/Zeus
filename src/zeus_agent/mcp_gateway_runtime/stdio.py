from __future__ import annotations

import json
import subprocess
import sys
import threading
from typing import IO, Optional

from pydantic import JsonValue

from .gateway import DownstreamServer, GatewaySession, McpGateway

_PROTOCOL_VERSION = "2025-06-18"


class StdioMcpClient:
    """Minimal newline-delimited JSON-RPC client for one downstream server."""

    def __init__(self, name: str, command: list[str]) -> None:
        self.name = name
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self._lock = threading.Lock()
        self._next_id = 0
        self._request("initialize", {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "zeus-mcp-gateway", "version": "1.0"},
        })
        self._notify("notifications/initialized", {})

    def list_tools(self) -> list[dict[str, JsonValue]]:
        result = self._request("tools/list", {})
        tools = result.get("tools") if isinstance(result, dict) else None
        return [tool for tool in tools if isinstance(tool, dict)] if isinstance(tools, list) else []

    def call_tool(self, name: str, arguments: dict[str, JsonValue]) -> dict[str, JsonValue]:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        return result if isinstance(result, dict) else {}

    def downstream(self) -> DownstreamServer:
        return DownstreamServer(name=self.name, list_tools=self.list_tools, call_tool=self.call_tool)

    def close(self) -> None:
        self._process.terminate()

    def _request(self, method: str, params: dict[str, JsonValue]) -> dict[str, JsonValue]:
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            while True:
                line = self._process.stdout.readline() if self._process.stdout else ""
                if not line:
                    raise RuntimeError("downstream {0} closed".format(self.name))
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if isinstance(message, dict) and message.get("id") == request_id:
                    if "error" in message:
                        raise RuntimeError(str(message["error"]))
                    result = message.get("result")
                    return result if isinstance(result, dict) else {}

    def _notify(self, method: str, params: dict[str, JsonValue]) -> None:
        with self._lock:
            self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _write(self, message: dict[str, JsonValue]) -> None:
        if self._process.stdin is None:
            raise RuntimeError("downstream stdin closed")
        self._process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self._process.stdin.flush()


def serve_stdio(
    gateway: McpGateway,
    session: GatewaySession,
    *,
    stdin: Optional[IO[str]] = None,
    stdout: Optional[IO[str]] = None,
) -> None:
    """Host-facing MCP server loop: the host config points at `zeus gateway`."""
    reader = stdin if stdin is not None else sys.stdin
    writer = stdout if stdout is not None else sys.stdout
    for line in reader:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            continue
        if not isinstance(message, dict) or "method" not in message:
            continue
        method = str(message.get("method"))
        request_id = message.get("id")
        if request_id is None:
            continue  # notifications need no reply
        if method == "initialize":
            result: dict[str, JsonValue] = {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "zeus-mcp-gateway", "version": "1.0"},
            }
            _reply(writer, request_id, result)
        elif method == "tools/list":
            _reply(writer, request_id, {"tools": gateway.tools_for_host()})
        elif method == "tools/call":
            params = message.get("params")
            params = params if isinstance(params, dict) else {}
            name = str(params.get("name", ""))
            arguments = params.get("arguments")
            arguments = arguments if isinstance(arguments, dict) else {}
            outcome = gateway.call_tool(session, name, arguments)
            if outcome.ok and outcome.result is not None:
                _reply(writer, request_id, outcome.result)
            else:
                _reply_error(writer, request_id, outcome.error or "denied", outcome.error_code)
        else:
            _reply_error(writer, request_id, "method not supported: {0}".format(method), "unsupported")


def _reply(writer: IO[str], request_id: JsonValue, result: dict[str, JsonValue]) -> None:
    writer.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}, ensure_ascii=False) + "\n")
    writer.flush()


def _reply_error(
    writer: IO[str], request_id: JsonValue, message: str, code: Optional[str]
) -> None:
    writer.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": message, "data": {"zeus_code": code}},
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    writer.flush()
