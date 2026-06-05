# Security Policy

Zeus is governed and local-first by default.

## Defaults

- No remote telemetry is enabled by the package.
- Local runtime state should stay outside source control.
- Provider credentials should be referenced by environment variable or external secret manager name, never copied into configs, tests, logs, or evidence.
- Secret-looking values are redacted in runtime surfaces that handle credential-like text.
- Tool, connector, transport, gateway, and live provider paths should pass through authority, lease, and evidence boundaries before execution.
- Dry-run and live-capable paths should remain distinguishable in code and review.

## Current v0.7.0 Boundary

`v0.7.0` is a governed Tool Limbs source checkpoint. It includes deterministic local scenarios, provider and tool interfaces, native tool catalog reporting, MCP discovery and API connector dry-run contracts, transport state, gateway/workflow scaffolds, verification surfaces, security planning, runtime lease scope checks, research evidence graph contracts, ontology candidate controls, sandbox workflow hints, live opt-in boundaries, public/private release boundaries, and release-gated hard-close reporting. It is not a hard-isolated remote execution platform by itself.

Before production use, live MCP tools, external AI APIs, browser/terminal automation, cron workers, remote sandboxes, and networked gateways should be wired through explicit authority grants, runtime leases, credential-scope binding, human approval when needed, sandbox egress policy, audit evidence, and rollback behavior.

See [docs/live-connection-architecture.md](docs/live-connection-architecture.md) for the target live connection design.

## Reporting

Please report security issues privately before public disclosure.
