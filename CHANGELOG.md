# Changelog

All notable changes to Zeus Agent are recorded here.

## v0.2.0 - 2026-06-02

### Added

- Total architecture runtime slice for Hermes/OpenClaw absorption planning.
- Security planning contracts for live-capable provider, MCP, web, gateway, network, plugin, and sandbox surfaces.
- Runtime lease credential-scope checks and fail-closed security decisions before handler execution.
- Source-pinned research evidence graph contracts with no-secret-echo checks.
- Provenance-backed ontology candidate contracts that remain proposed or blocked until review.
- Sandbox workflow optimization hints that do not execute commands.
- Dry-run parallel orchestration scheduler with dependency, evidence, depth, live-surface, and write-scope checks.
- Public `total-plan`, `total-blocks`, and `total-eval` CLI/eval surfaces.
- Public live connection architecture blueprint for future AI API, MCP, tool, gateway, web, browser, terminal, and sandbox adapters.

### Notes

- `v0.2.0` is still intentionally local-first and deterministic by default.
- Live external execution is designed but not claimed as production-active. Real provider, MCP, gateway, browser, terminal, and sandbox adapters must be wired through authority grants, runtime leases, credential scopes, approval receipts, sandbox egress controls, audit evidence, and rollback behavior.
- Private Codex/ULW artifacts, local evidence, local runtime databases, and machine-local operating state remain excluded from the public release.

## v0.1.0 - 2026-06-02

### Added

- First public Zeus Agent release.
- Mneme-style README presentation with a Zeus header banner, badges, navigation, architecture map, evidence table, and readiness boundary.
- Public Hermes comparison document covering Hermes baseline architecture, Zeus target architecture, and the governed runtime differences.
- Governed objective compiler and runtime contract surface.
- Authority-gated capability broker with evidence records.
- Local agent work loop, conversation, provider, tool, connector, transport, gateway, workflow, verification, and skill-evolution scaffolds.
- CLI eval commands for deterministic local runtime validation.
- Public packaging metadata, README, CI, and release baseline.

### Notes

- Local Codex control packs, private planning notes, evidence logs, runtime databases, and internal operating artifacts are intentionally excluded from the public release.
- Live external provider, MCP, gateway, browser, terminal, and remote execution should be wired through the existing authority, lease, and evidence boundaries before production use.
