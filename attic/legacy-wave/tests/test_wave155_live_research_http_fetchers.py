from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from zeus_agent.live_research_adapter_catalog_runtime import live_research_adapter_catalog_payload
from zeus_agent.live_research_community_owned_client import (
    CommunityResearchHttpRequest,
    CommunityResearchOwnedClient,
    UrlLibCommunityResearchHttpFetcher,
)
from zeus_agent.live_research_github_owned_client import (
    GitHubResearchOwnedClient,
    ResearchHttpRequest,
    UrlLibResearchHttpFetcher,
)
from zeus_agent.live_research_owned_client_transport_runtime import LiveResearchOwnedClientRequest
from zeus_agent.live_research_web_owned_client import (
    UrlLibWebResearchHttpFetcher,
    WebResearchHttpRequest,
    WebResearchOwnedClient,
)


def test_url_lib_research_fetchers_parse_json_and_redact_payloads() -> None:
    server = _ResearchGetServer()
    server.start()
    try:
        github = UrlLibResearchHttpFetcher().fetch(ResearchHttpRequest(url=f"{server.base_url}/github", timeout_ms=2000))
        web = UrlLibWebResearchHttpFetcher().fetch(WebResearchHttpRequest(url=f"{server.base_url}/web", timeout_ms=2000))
        community = UrlLibCommunityResearchHttpFetcher().fetch(
            CommunityResearchHttpRequest(url=f"{server.base_url}/community", timeout_ms=2000),
        )
    finally:
        server.shutdown()

    serialized = json.dumps({"github": github.payload, "web": web.payload, "community": community.payload})
    assert github.status_code == 200
    assert web.status_code == 200
    assert community.status_code == 200
    assert github.payload["items"][0]["full_name"] == "Orvek-dev/Zeus"
    assert web.payload["items"][0]["title"] == "Zeus live notes"
    assert community.payload["items"][0]["title"] == "Parallel agent workflow"
    assert "ghp_" + "wave155" not in serialized
    assert server.request_count == 3
    assert server.shutdown_complete is True


def test_url_lib_owned_clients_emit_loopback_receipts_without_production_claim() -> None:
    server = _ResearchGetServer()
    server.start()
    try:
        github_receipt = GitHubResearchOwnedClient(
            fetcher=UrlLibResearchHttpFetcher(),
            endpoint=f"{server.base_url}/github",
        ).search(_request("github"))
        web_receipt = WebResearchOwnedClient(
            fetcher=UrlLibWebResearchHttpFetcher(),
            endpoint=f"{server.base_url}/web",
        ).search(_request("web"))
        community_receipt = CommunityResearchOwnedClient(
            fetcher=UrlLibCommunityResearchHttpFetcher(),
            endpoint=f"{server.base_url}/community",
        ).search(_request("community"))
    finally:
        server.shutdown()

    for receipt in (github_receipt, web_receipt, community_receipt):
        assert receipt.status_code == 200
        assert receipt.result_count == 1
        assert receipt.network_opened is True
        assert receipt.non_loopback_network_opened is False
        assert receipt.cleanup_receipt == "research-owned-client-closed"


def test_live_research_catalog_marks_real_fetchers_available_but_not_production_ready() -> None:
    payload = live_research_adapter_catalog_payload()

    assert payload["production_ready_count"] == 0
    assert all(adapter["real_fetcher_available"] is True for adapter in payload["adapters"])
    assert all(adapter["production_fetcher_configured"] is False for adapter in payload["adapters"])
    assert payload["network_opened"] is False
    assert payload["live_production_claimed"] is False


def _request(source_id: str) -> LiveResearchOwnedClientRequest:
    return LiveResearchOwnedClientRequest(
        policy_id=f"live-research-policy://wave155/{source_id}",
        source_id=source_id,
        query="parallel coding workflow",
        source_pin_ref=f"source-pin://wave155/{source_id}",
        max_results=5,
        rate_limit_per_minute=30,
    )


class _ResearchGetServer:
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
                if self.path.startswith("/github"):
                    self._send_json({"items": [{"full_name": "Orvek-dev/Zeus", "html_url": "https://github.com/Orvek-dev/Zeus"}], "debug": "ghp_" + "wave155"})
                elif self.path.startswith("/web"):
                    self._send_json({"items": [{"title": "Zeus live notes", "url": "https://docs.example.dev/zeus-live"}], "debug": "ghp_" + "wave155"})
                elif self.path.startswith("/community"):
                    self._send_json({"items": [{"title": "Parallel agent workflow", "url": "https://community.example.dev/t/parallel"}], "debug": "ghp_" + "wave155"})
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                return None

            def _send_json(self, payload: dict[str, object]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler
