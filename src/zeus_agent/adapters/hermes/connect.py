from __future__ import annotations

import shlex

from pydantic import JsonValue


def hermes_connect_bundle(
    *,
    zeusd_url: str = "http://127.0.0.1:8788",
    pair_code: str = "<run pairing first>",
    default_model: str = "gpt-5.4",
    zeus_bin: str = "zeus",
    zeus_home: str | None = None,
) -> dict[str, JsonValue]:
    """Everything a hermes config needs to ride all three gates, in the schema
    hermes v0.16.x actually accepts.

    Two findings from real dogfood are baked in:
    - hooks are SHELL hooks (``[{command, ...}]``), not HTTP hooks. The command
      reads the tool-call JSON on stdin and returns the decision JSON on stdout
      via ``zeus hook hermes`` — no separate signing dance for the local case.
    - the model goes through a NAMED provider, not a bare ``base_url``. A bare
      loopback base_url makes hermes treat Zeus as a keyless local LLM and send
      ``no-key-required`` upstream; a named provider with ``key_env`` passes the
      real upstream key through Zeus instead.
    """
    pre_hook = _hook_command(zeus_bin=zeus_bin, event="pre", zeus_home=zeus_home)
    post_hook = _hook_command(zeus_bin=zeus_bin, event="post", zeus_home=zeus_home)
    return {
        "config_yaml_patch": {
            "providers": {
                "zeus": {
                    "api": "{0}/v1".format(zeusd_url),
                    "key_env": "OPENAI_API_KEY",
                    "default_model": default_model,
                    "transport": "chat_completions",
                }
            },
            "model": {
                "provider": "zeus",
                "default": default_model,
                "default_headers": {
                    "x-zeus-host": "hermes",
                    "x-zeus-principal": "agent.hermes",
                },
            },
            "mcp_servers": {"zeus-gateway": {"command": [zeus_bin, "gateway"]}},
            "hooks": {
                "pre_tool_call": [{"command": pre_hook, "matcher": "*"}],
                "post_tool_call": [{"command": post_hook, "matcher": "*"}],
            },
        },
        "allowlist": {
            "why": "hermes gates shell hooks behind an explicit allowlist even with hooks_auto_accept",
            "step": "approve once: `hermes --accept-hooks`, or add the two commands to "
            "~/.hermes/shell-hooks-allowlist.json",
        },
        "pairing": {
            "request": "POST {0}/zeus/pair/request {{\"host\": \"hermes\"}}".format(zeusd_url),
            "human_step": "zeus pair --approve <CODE>",
            "never": "do not skip approval — a silent policy-server swap is total compromise",
            "code_hint": pair_code,
        },
        "proxy_note": "run the proxy with `--hook-owned-host hermes` so the tool_call gate "
        "defers soft asks to the blocking pre_tool_call hook (no double prompt)",
        "session_recovery": "GET {0}/zeus/brief?session_id=<sid>&principal_id=agent.hermes".format(
            zeusd_url
        ),
    }


def _hook_command(*, zeus_bin: str, event: str, zeus_home: str | None) -> str:
    parts = [zeus_bin, "hook", "hermes", "--event", event]
    if zeus_home is not None:
        parts.extend(["--home", zeus_home])
    return shlex.join(parts)
