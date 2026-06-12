# Connecting a host agent to Zeus

[English](CONNECTING.md) · [한국어](CONNECTING.ko.md)

Zeus is a local-first governance control plane: your agent keeps doing the
work; Zeus decides, records, approves, and blocks at four gates (LLM proxy ·
MCP gateway · decision hooks · egress ring). Model keys stay on the host side.

```
zeus init                 # create ~/.zeus/control-plane
zeus proxy --upstream https://api.openai.com   # zeusd: /v1 proxy + /zeus API
```

Pairing is **never zero-confirm**: when an agent asks to connect, it shows a
code and you approve it yourself — a silently swapped policy server is total
compromise.

```
zeus pair --approve ZEUS-XXXX
```

## Claude Code (Gate 0 — PreToolUse/PostToolUse hook)

```
zeus connect claude-code --write --project-dir .
```

Every tool call now flows through `decide()`; outcomes flow back through
`record()`. Check `zeus status` (coverage, asks, chain) and
`zeus ledger --tail 20`.

## hermes-agent (blocking pre_tool_call hook + proxy + gateway)

```
zeus connect hermes          # prints the config.yaml patch + pairing steps
zeus connect hermes --check  # preflight: proxy up / home ready / manual checklist
```

- **Named provider, not a bare base_url.** The patch sets a `providers.zeus`
  entry (`api: http://127.0.0.1:8788/v1`, `key_env: OPENAI_API_KEY`) and
  `model.provider: zeus`. A bare loopback `base_url` makes hermes treat Zeus as
  a keyless local LLM and send `no-key-required` upstream. The patch also sets
  `model.default_headers.x-zeus-host: hermes`, which is how the `/v1` proxy
  selects the Hermes tool catalog.
- **Shell hooks** (the schema hermes v0.16.x accepts): `pre_tool_call` /
  `post_tool_call` run `zeus hook hermes --event pre|post` (JSON on stdin,
  decision JSON on stdout). Allowlist them once: `hermes hooks doctor`.
- `mcp_servers` → `zeus gateway` (quarantine, rug-pull defense).
- Run the proxy with `--hook-owned-host hermes` so the tool_call gate **defers
  a soft ask to the blocking hook** — you are asked once, not twice.
- Subagents are attenuated child principals: out-of-envelope is **denied**.
- Session recovery: `GET /zeus/brief?session_id=...` returns the receipt
  timeline — scoped, masked, ledgered, and tagged untrusted.
- A parked ASK is resolvable: `zeus approvals --pending` then
  `zeus approve --parked <id>` (a soft ask becomes a one-time pass; hard-risk
  is approved per-instance, never licensed).

## OpenClaw (proxy-primary + exec approval relay)

```
zeus connect openclaw    # prints provider/MCP patches + the relay contract
```

- `baseUrl` → the proxy (`/v1`): tool_calls are intercepted in the response
  stream, since non-exec tools have no pre-hook.
- exec → Zeus subscribes to `exec.approval.requested` as an operator client
  and resolves with receipts; dangerous commands park until you answer.
- ClawHub self-onboarding: the `zeus-connect` skill walks the agent through
  the steps above — the pairing approval still lands on you.

## Budgets, policy, rhythm

```
zeus budget --scope objective --id obj.email --limit 2000000   # micro-USD
zeus policy --apply safe-assistant --confirm
zeus policy --rule "weekly budget $12" --confirm
zeus digest            # weekly summary; `--ack` resets the dead-man switch
```

An unacked digest demotes autonomy (side-effecting calls ask until you're
back). First-seen hosts/recipients escalate once, then are learned.
