# Security Policy

Zeus is governed and local-first by default.

## Defaults

- No remote telemetry is enabled by the package.
- Local runtime state should stay outside source control.
- Provider credentials should be referenced by environment variable or external secret manager name, never copied into configs, tests, logs, or evidence.
- Secret-looking values are redacted in runtime surfaces that handle credential-like text.
- Tool, connector, transport, gateway, and live provider paths should pass through authority, lease, and evidence boundaries before execution.
- Dry-run and live-capable paths should remain distinguishable in code and review.

## Current v5.0.0 Boundary

`v5.0.0` keeps Zeus local-first and governed by default. The public package exposes
productized status, goal intelligence, cognitive-provider activation, provider/MCP/tool
runtime contracts, memory/ontology surfaces, self-evolution review queues, and
ObjectiveRun start/status/export surfaces. It also exposes the Governed Live Slice
authority UX for missing objective, lease, approval, broker-evidence,
credential-scope, sandbox-policy, and audit-receipt requirements, plus the Live
Platform Beta aggregate status/operator journey, but it does not enable unrestricted
production live execution.

Governed live-capable work must resolve to trusted authority, lease, approval,
credential-scope, sandbox, audit, and evidence records before a handler can execute or a
production-ready claim can pass. Public reference strings alone do not authorize
dispatch. Raw credential material is blocked or redacted before public output.

This release still does not claim production external provider execution, remote MCP
production execution, hosted API daemon readiness, external gateway/webhook production
execution, browser live execution, remote sandbox execution, unrestricted production live
readiness, unattended execution, self-modifying workflows, automatic memory writes from
ordinary agent turns, ontology promotion, learned-rule promotion, active rule writes,
active skill writes, workflow pattern promotion, or hard-isolated remote execution by
itself.

Before production use, live MCP tools, external AI APIs, browser/terminal automation, cron workers, remote sandboxes, networked gateways, and memory/ontology promotion paths should be wired through explicit authority grants, runtime leases, credential-scope binding, retention policy, human approval when needed, sandbox egress policy, audit evidence, and rollback behavior.

See [docs/live-connection-architecture.md](docs/live-connection-architecture.md) for the target live connection design.

## Reporting

Please report security issues privately before public disclosure.
