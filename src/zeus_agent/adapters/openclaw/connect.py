from __future__ import annotations

from pydantic import JsonValue


def openclaw_connect_bundle(
    *,
    zeusd_url: str = "http://127.0.0.1:8788",
) -> dict[str, JsonValue]:
    """OpenClaw rides three gates: base_url → proxy (PRIMARY — tool_calls are
    intercepted in the response, since non-exec tools have no pre-hook), MCP →
    gateway, exec → the approval relay (operator client)."""
    return {
        "provider_patch": {
            "baseUrl": "{0}/v1".format(zeusd_url),
            "note": "keys stay in OpenClaw config; the proxy forwards auth headers",
        },
        "mcp_patch": {"servers": {"zeus-gateway": {"command": ["zeus", "gateway"]}}},
        "exec_relay": {
            "subscribe": "exec.approval.requested",
            "resolve": "exec.approval.resolve",
            "operator": "zeusd connects as an operator client and answers with receipts",
        },
        "log_hygiene": (
            "the proxy counts secret-shaped material in responses (OpenClaw "
            ".env/log leakage class) — watch `zeus status` → proxy.secret_findings"
        ),
        "pairing": {
            "request": "POST {0}/zeus/pair/request {{\"host\": \"openclaw\"}}".format(zeusd_url),
            "human_step": "zeus pair --approve <CODE>",
            "never": "no zero-confirm onboarding — a policy-server swap is total compromise",
        },
    }


def zeus_connect_skill(*, zeusd_url: str = "http://127.0.0.1:8788") -> str:
    """The ClawHub-style self-onboarding skill body (markdown)."""
    return (
        "# zeus-connect\n\n"
        "Connect this agent to the Zeus governance control plane.\n\n"
        "1. Point the model provider at the governed proxy: set `baseUrl` to\n"
        "   `{0}/v1` (keep your API keys where they are).\n"
        "2. Replace direct MCP servers with the gateway: `zeus gateway`.\n"
        "3. Request pairing: `POST {0}/zeus/pair/request` with this host's name,\n"
        "   then SHOW THE CODE TO THE HUMAN and wait.\n"
        "4. The human approves with `zeus pair --approve <CODE>`. Never proceed\n"
        "   without it; never reconfigure the policy URL silently.\n"
        "5. Verify: `GET {0}/v1/health` and run one read-only action; check it\n"
        "   appears in `zeus ledger --tail 5`.\n"
    ).format(zeusd_url)
