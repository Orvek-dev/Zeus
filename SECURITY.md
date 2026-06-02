# Security Policy

Zeus is governed and local-first by default.

## Defaults

- No remote telemetry is enabled by the package.
- Local runtime state should stay outside source control.
- Provider credentials should be referenced by environment variable or external secret manager name, never copied into configs, tests, logs, or evidence.
- Secret-looking values are redacted in runtime surfaces that handle credential-like text.
- Tool, connector, transport, gateway, and live provider paths should pass through authority, lease, and evidence boundaries before execution.
- Dry-run and live-capable paths should remain distinguishable in code and review.

## Current v1.0.0 Boundary

`v1.0.0` is a governed runtime foundation. It includes deterministic local scenarios, provider and tool interfaces, transport state, gateway/workflow scaffolds, and verification surfaces. It is not a hard-isolated remote execution platform by itself.

Before production use, live MCP tools, external AI APIs, browser/terminal automation, cron workers, remote sandboxes, and networked gateways should be wired through explicit authority grants, runtime leases, audit evidence, and rollback behavior.

## Reporting

Please report security issues privately before public disclosure.
