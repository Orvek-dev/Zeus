> **ARCHIVED — pre-refoundation record (v0.x–v6.x agent-platform line).** Kept verbatim for the parked conformance harness. The current product is the local-first governance control plane described in [README.md](../README.md); where this document disagrees with the README, the README wins.

# Zeus Hermes Live Opt-In Boundary

This document is the W209 release-candidate boundary for absorbing Hermes-style
live platform breadth into Zeus without claiming production live readiness.

## Position

Zeus can expose Hermes-like entrypoints: CLI, gateway, ACP, batch runner, API
server, Python library, MCP, tools, memory, and skills. In the current RC these
surfaces are local-ready and policy-bound, not production-live.

## Live-Capable Surfaces

| Surface | Hermes capability | Zeus boundary |
| --- | --- | --- |
| `provider_api` | provider resolution | objective contract, scoped credential lease, provider preflight |
| `mcp_tools` | MCP tool dispatch | server provenance, include/exclude policy, credential binding |
| `gateway_delivery` | messaging gateway | loopback/auth/pairing first, target allowlist before delivery |
| `browser_web` | browser and web backends | research preflight, source pinning, prompt-injection quarantine |
| `terminal_sandbox` | terminal and sandbox backend | mount/network/resource lease before execution |
| `cron_batch` | cron and batch runner | headless approval, recursion guard, idempotency, cleanup receipt |
| `plugin_supply_chain` | plugins and toolsets | manifest/hash/dependency policy and quarantine |
| `memory_ontology` | memory and skills | local proposed records, review before active rules |
| `api_acp` | API server and ACP | local adapter readiness before public binding |

## Required Opt-In Steps

1. Bind the user objective to an authority lease.
2. Resolve credentials through scoped refs without raw material echo.
3. Run live preflight for the exact provider, MCP, gateway, browser, terminal,
   sandbox, cron, plugin, or API surface.
4. Ask for explicit human approval when the action can mutate state, spend
   money, deliver externally, access credentials, or run outside loopback.
5. Capture trace, cleanup, rollback, and security evidence.
6. Pass a separate project-mode release gate before any production-live claim.

## RC Claim

The W209 RC claim is:

`Hermes-like live breadth is mapped and ready for explicit opt-in design, but
production live readiness remains blocked until separate project-mode release
evidence exists.`

This guide does not authorize network execution, credential use, external
handler invocation, hosted API binding, release publication, push, tag, or
deployment promotion.
