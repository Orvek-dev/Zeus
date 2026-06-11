> **ARCHIVED — pre-refoundation record (v0.x–v6.x agent-platform line).** Kept verbatim for the parked conformance harness. The current product is the local-first governance control plane described in [README.md](../README.md); where this document disagrees with the README, the README wins.

# Zeus Public/Private Boundary

This document is the W210 release-candidate security boundary for publishing
Zeus as a public project while preserving local harness, evidence, and private
operator artifacts.

## Public Surface

The public package may expose:

- `README.md`
- `SECURITY.md`
- `CHANGELOG.md`
- packaged source under `src/`
- tests that do not contain real credential material
- public architecture documents such as `docs/live-connection-architecture.md`
  and `docs/zeus-hermes-live-opt-in-boundary.md`

## Private Surface

The following remain local/private by default and are ignored in this checkout:

- `.agents/`
- `.codex/`
- `.omo/`
- `AGENTS.md`
- `ETHOS.md`
- `docs/ai/`
- `gstack/`
- `harness/`
- `plans/`
- `scripts/harness/`
- `spec/`
- `templates/`
- `evidence/`

## Release Boundary

This non-git working directory is not a release publication source. Public
release, tag, push, GitHub release, and production-live claims remain blocked
until a separate git-backed project-mode release gate passes with rollback,
security review, and live-surface evidence.

## Security Boundary

RC evidence must keep these values false unless a later release spec explicitly
authorizes otherwise:

- `credential_material_accessed`
- `network_opened`
- `external_delivery_opened`
- `handler_executed`
- `live_production_claimed`

Raw secret-like text must never be copied into docs, logs, evidence, memory,
test output, release notes, or public package metadata.
