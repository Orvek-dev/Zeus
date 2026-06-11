from __future__ import annotations

from pydantic import JsonValue


def hermes_connect_bundle(
    *,
    zeusd_url: str = "http://127.0.0.1:8788",
    pair_code: str = "<run pairing first>",
) -> dict[str, JsonValue]:
    """Everything a hermes config needs to ride all three gates.

    The agent can apply this itself ("Zeus에 연결해줘") — but the pairing code
    must still be approved by the human (`zeus pair --approve CODE`): config
    self-onboarding is automated, trust is not.
    """
    return {
        "config_yaml_patch": {
            "model": {"base_url": "{0}/v1".format(zeusd_url)},
            "mcp_servers": {
                "zeus-gateway": {"command": ["zeus", "gateway"]}
            },
            "hooks": {
                "pre_tool_call": {
                    "type": "http",
                    "url": "{0}/zeus/decide".format(zeusd_url),
                    "blocking": True,
                    "signing": {
                        "headers": {
                            "x-zeus-pair-code": pair_code,
                            "x-zeus-timestamp": "<iso8601-now>",
                            "x-zeus-signature": "<hmac-sha256(secret, timestamp + '.' + body)>",
                        }
                    },
                },
                "post_tool_call": {
                    "type": "http",
                    "url": "{0}/zeus/record".format(zeusd_url),
                },
            },
        },
        "pairing": {
            "request": "POST {0}/zeus/pair/request {{\"host\": \"hermes\"}}".format(zeusd_url),
            "human_step": "zeus pair --approve <CODE>",
            "never": "do not skip approval — a silent policy-server swap is total compromise",
        },
        "session_recovery": "GET {0}/zeus/brief?session_id=<sid>&principal_id=agent.hermes".format(
            zeusd_url
        ),
    }
