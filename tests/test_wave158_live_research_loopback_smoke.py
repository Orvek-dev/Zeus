from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from zeus_agent.library_runtime import ZeusAgent
from zeus_agent.live_research_activation_policy_runtime import LiveResearchActivationPolicyRuntime
from zeus_agent.live_research_execution_plan_runtime import LiveResearchExecutionPlanRuntime
from zeus_agent.live_research_loopback_smoke_runtime import LiveResearchLoopbackSmokeRuntime
from zeus_agent.live_research_source_config_runtime import LiveResearchSourceConfigRuntime


def test_loopback_smoke_executes_planned_web_research_without_production_claim() -> None:
    server = _SmokeServer()
    server.start()
    try:
        plan = _plan(adapter_id="web", source_id="web", endpoint=f"{server.base_url}/web")
        result = LiveResearchLoopbackSmokeRuntime().execute(plan=plan)
    finally:
        server.shutdown()

    payload = result.to_payload()
    assert payload["decision"] == "smoke_executed"
    assert payload["source_id"] == "web"
    assert payload["result_count"] == 1
    assert payload["network_opened"] is True
    assert payload["non_loopback_network_opened"] is False
    assert payload["live_production_claimed"] is False
    assert "ghp_" + "wave158" not in json.dumps(payload)
    assert server.request_count == 1
    assert server.shutdown_complete is True


def test_loopback_smoke_blocks_non_loopback_execution_plan_before_network() -> None:
    plan = _plan(adapter_id="web", source_id="web", endpoint="https://search.example.dev/query")

    result = LiveResearchLoopbackSmokeRuntime().execute(plan=plan)

    assert result.decision == "blocked"
    assert "live_research_smoke_endpoint_not_loopback" in result.blocked_reasons
    assert result.network_opened is False
    assert result.client_constructed is False


def test_loopback_smoke_cli_and_library_surface_match() -> None:
    server = _SmokeServer()
    server.start()
    try:
        plan = _plan(adapter_id="community", source_id="community", endpoint=f"{server.base_url}/community")
        env = {**os.environ, "PYTHONPATH": "src"}
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "zeus_agent",
                "live-research-loopback-smoke",
                "--plan-json",
                plan.model_dump_json(),
                "--json",
            ],
            cwd=".",
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        library_payload = ZeusAgent().live_research_loopback_smoke(plan=plan.to_payload())
    finally:
        server.shutdown()

    assert proc.returncode == 0, proc.stderr
    cli_payload = json.loads(proc.stdout)
    assert _stable_payload(cli_payload) == _stable_payload(library_payload)
    assert cli_payload["decision"] == "smoke_executed"
    assert cli_payload["network_opened"] is True
    assert cli_payload["non_loopback_network_opened"] is False


def _plan(*, adapter_id: str, source_id: str, endpoint: str):
    config = LiveResearchSourceConfigRuntime().configure(
        adapter_id=adapter_id,
        endpoint=endpoint,
        allow_loopback_smoke=True,
    )
    policy = LiveResearchActivationPolicyRuntime().plan(
        source_id=source_id,
        query="parallel coding workflow",
        live_search_requested=True,
        approval_ref=f"approval://research/{source_id}",
        source_pin_ref=f"source-pin://research/{source_id}",
        max_results=5,
        rate_limit_per_minute=30,
    )
    return LiveResearchExecutionPlanRuntime().plan(
        source_config=config,
        policy=policy,
        execution_ref=f"live-research-execution://wave158/{source_id}",
    )


def _stable_payload(payload: dict[str, object]) -> dict[str, object]:
    return {
        "decision": payload["decision"],
        "adapter_id": payload["adapter_id"],
        "source_id": payload["source_id"],
        "result_count": payload["result_count"],
        "network_opened": payload["network_opened"],
        "non_loopback_network_opened": payload["non_loopback_network_opened"],
        "live_production_claimed": payload["live_production_claimed"],
    }


class _SmokeServer:
    def __init__(self) -> None:
        self.request_count = 0
        handler = self._handler()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self.shutdown_complete = False

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return "http://{0}:{1}".format(host, port)

    def start(self) -> None:
        self._thread.start()

    def shutdown(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
        self.shutdown_complete = not self._thread.is_alive()

    def _handler(self):
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parent.request_count += 1
                title = "Parallel agent workflow" if self.path.startswith("/community") else "Zeus live notes"
                payload = {
                    "items": [{"title": title, "url": "https://docs.example.dev/zeus-live"}],
                    "debug": "ghp_" + "wave158",
                }
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return None

        return Handler
