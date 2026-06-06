# Security Policy

Zeus is governed and local-first by default.

## Defaults

- No remote telemetry is enabled by the package.
- Local runtime state should stay outside source control.
- Provider credentials should be referenced by environment variable or external secret manager name, never copied into configs, tests, logs, or evidence.
- Secret-looking values are redacted in runtime surfaces that handle credential-like text.
- Tool, connector, transport, gateway, and live provider paths should pass through authority, lease, and evidence boundaries before execution.
- Dry-run and live-capable paths should remain distinguishable in code and review.

## Current v2.1.0 Boundary

`v2.1.0` keeps the v2.0.0 governed live platform boundary and adds the Kernel-Throughput Integration runtime. Governed live-capable work must resolve to a trusted governance record containing the lease, approval, promotion guard, and broker evidence target before a handler can execute; public reference strings alone do not authorize dispatch. The allowed deterministic provider smoke path is mediated by `CapabilityBroker`, scoped `AuthorityContext`, `ApprovalReceipt`, `LiveTransportPromotionGuard`, and broker dispatch evidence. Raw credential material is blocked before dispatch, and `release-gated-ulw --target-version v2.1.0 --json` reports `broker_evidence_required` until broker evidence is recorded. This release still does not claim production external provider execution, remote MCP production execution, hosted API daemon readiness, external gateway/webhook production execution, browser live execution, remote sandbox execution, unrestricted production live readiness, unattended execution, self-modifying workflows, automatic memory writes from ordinary agent turns, ontology promotion, learned-rule promotion, active rule writes, active skill writes, workflow pattern promotion, or hard-isolated remote execution by itself.

Before production use, live MCP tools, external AI APIs, browser/terminal automation, cron workers, remote sandboxes, networked gateways, and memory/ontology promotion paths should be wired through explicit authority grants, runtime leases, credential-scope binding, retention policy, human approval when needed, sandbox egress policy, audit evidence, and rollback behavior.

See [docs/live-connection-architecture.md](docs/live-connection-architecture.md) for the target live connection design.

## Reporting

Please report security issues privately before public disclosure.
