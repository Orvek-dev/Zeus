# Changelog

All notable changes to Zeus Agent are recorded here.

## v1.0.0-rc.1 - 2026-06-06

### Added

- Production Foundation runtime and CLI command for identity/auth, approval,
  runtime lease, credential binding, secret resolver, audit, sandbox, rollback,
  and independent-review boundary reporting.
- Release-gated `v1.0.0-rc.1` checkpoint fields for the production foundation
  contract and required ULW manual QA evidence.
- Python library facade method for `production_foundation(...)` so library
  callers can inspect the same production foundation contract as the CLI.
- Secret-safe production foundation operator-note handling that blocks
  credential-like notes without echoing raw secret-like material.

### Changed

- Version metadata is aligned to `zeus-agent==1.0.0rc1` for Python packaging
  and `v1.0.0-rc.1` for the GitHub release tag.
- README, Hermes comparison, live connection architecture, and security policy
  now describe the Production Foundation checkpoint on top of the earlier Live
  Beta Candidate boundary.

### Notes

- `v1.0.0-rc.1` is still local-first and deterministic by default.
- The Production Foundation can report that required safety/control runtimes are
  present, but it does not claim production live readiness, hosted SaaS
  readiness, unattended execution, or hard-isolated remote runtime operation.

## v1.0.0-rc - 2026-06-05

### Added

- Live Beta Candidate runtime and CLI command for release-candidate live beta
  readiness, opt-in smoke, live cockpit, rollback, review, approval, and lease
  boundary reporting.
- Release-gated `v1.0.0-rc` checkpoint fields for live beta candidate
  contracts, live readiness, opt-in smoke, live cockpit, live beta activation,
  RC closeout, and no-production readiness.
- Python library facade method for `live_beta_candidate(...)` so library
  callers can inspect the same RC contract as the CLI.
- Secret-safe operator-note handling that blocks credential-like RC notes
  without echoing raw secret-like material.

### Changed

- Version metadata is aligned to `zeus-agent==1.0.0rc0` for Python packaging
  and `v1.0.0-rc` for the GitHub release tag.
- README, Hermes comparison, live connection architecture, master design, and
  security policy now describe the Live Beta Candidate checkpoint instead of
  only the `v0.10.0` Adaptive Zeus checkpoint.

### Notes

- `v1.0.0-rc` is still local-first and deterministic by default.
- The RC can claim live-beta candidate readiness from local opt-in smoke, but
  it does not claim production live readiness, hosted SaaS readiness,
  unattended execution, or hard-isolated remote runtime operation.

## v0.10.0 - 2026-06-05

### Added

- Adaptive Zeus runtime and CLI command for objective-sensitive ULW workflow
  selection across lean ULW, classify-and-act, parallel fan-out synthesis, and
  adversarial verification.
- Release-gated `v0.10.0` checkpoint fields for Adaptive Zeus readiness,
  dynamic workflow contracts, pattern routing, critique checkpoints, workflow
  learning visibility, trajectory/eval visibility, and dry-run evidence.
- Python library facade method for `adaptive_zeus_status(...)` so library
  callers can inspect the same adaptive workflow contract as the CLI.
- Secret-safe objective handling that blocks credential-like workflow requests
  without echoing raw secret-like material.

### Changed

- Version metadata is aligned to `zeus-agent==0.10.0`.
- README, Hermes comparison, live connection architecture, master design, and
  security policy now describe the Adaptive Zeus checkpoint instead of only the
  `v0.9.0` Memory/Ontology checkpoint.

### Notes

- `v0.10.0` is still local-first and deterministic by default.
- Adaptive workflow selection does not execute handlers, open network access,
  self-modify workflows, auto-write memory, promote learned rules, or widen
  authority.

## v0.9.0 - 2026-06-05

### Added

- Memory/Ontology Surface runtime and CLI command for local MemoryGraph, LLM
  Wiki, ontology review queue, skill-learning memory, and retention-policy
  boundary reporting.
- Release-gated `v0.9.0` checkpoint fields for Memory/Ontology readiness,
  local storage, LLM Wiki visibility, ontology review, no auto-promotion, and
  dry-run evidence.
- Python library facade method for `memory_ontology_status(...)` so library
  callers can inspect the same contract as the CLI.
- Secret-safe selector handling that blocks credential-like subject or
  candidate identifiers without echoing raw secret-like material.

### Changed

- Version metadata is aligned to `zeus-agent==0.9.0`.
- README, Hermes comparison, live connection architecture, master design, and
  security policy now describe the Memory/Ontology checkpoint instead of only
  the `v0.8.0` Platform Surface checkpoint.

### Notes

- `v0.9.0` is still local-first and deterministic by default.
- Memory writes remain proposed or quarantined local facts. Ontology terms,
  wiki pages, skill learnings, active rules, authority widening, and live
  transports are not auto-promoted without review.

## v0.8.0 - 2026-06-05

### Added

- Platform Surface runtime and CLI surface for governed CLI, API, gateway, ACP,
  batch, and Python library entrypoint boundary reporting.
- Release-gated `v0.8.0` checkpoint fields for Platform Surface readiness,
  entrypoint availability, approval lease, security gate, and dry-run evidence.
- Gateway entrypoint coverage in the platform cockpit without starting a daemon,
  opening network access, or enabling external delivery.
- Secret-safe Platform Surface handling that blocks unknown or credential-like
  surface identifiers without echoing raw secret-like material.

### Changed

- Version metadata is aligned to `zeus-agent==0.8.0`.
- README, Hermes comparison, live connection architecture, and security policy
  now describe the Platform Surface checkpoint instead of only the `v0.7.0`
  Tool Limbs checkpoint.

### Notes

- `v0.8.0` is still local-first and deterministic by default.
- Platform entrypoint visibility is not execution authorization. Hosted API,
  gateway delivery, ACP sessions, batch execution, browser/terminal automation,
  remote sandboxing, and external provider/MCP production execution remain gated
  behind explicit authority, lease, approval, sandbox, evidence, rollback, and
  release review.

## v0.7.0 - 2026-06-05

### Added

- Tool Limbs runtime and CLI surface for governed native tool, MCP discovery,
  and API connector boundary reporting.
- Release-gated `v0.7.0` checkpoint fields for Tool Limbs readiness,
  include/exclude policy, approval lease, security gate, and evidence capture.
- Secret-safe Tool Limbs adversarial handling that blocks unknown or
  credential-like tool identifiers without echoing raw secret-like material.

### Changed

- Version metadata is aligned to `zeus-agent==0.7.0`.
- README, Hermes comparison, live connection architecture, and security policy
  now describe the Tool Limbs checkpoint instead of only the `v0.6.0`
  live-spine checkpoint.

### Notes

- `v0.7.0` is still local-first and deterministic by default.
- Tool visibility is not execution authorization. Real external provider, MCP,
  gateway, browser, terminal, sandbox, and API production execution remains
  gated behind explicit authority, lease, approval, sandbox, evidence, rollback,
  and release review.

## v0.6.0 - 2026-06-05

### Added

- Release-gated ULW runtime and CLI surface for the sequential `v0.6.0` through
  `v1.0.0-rc` program.
- `v0.6.0` live-spine checkpoint reporting for provider loopback readiness, MCP
  loopback readiness, approval/lease requirements, manual QA, independent
  review, and GitHub release checkpoints.
- Secret-safe adversarial boundary handling for release-gated notes without
  echoing raw credential-like material.

### Changed

- Version metadata is aligned to `zeus-agent==0.6.0`.
- README evidence and readiness language now describe the live-spine release
  checkpoint instead of only the `v0.5.0` design checkpoint.

### Notes

- `v0.6.0` is still local-first and deterministic by default.
- Real external provider/MCP/gateway/browser/terminal/sandbox production
  execution remains gated behind explicit authority, lease, approval, sandbox,
  evidence, rollback, and release review.

## v0.5.0 - 2026-06-05

### Added

- Public sync of the expanded Zeus live-platform runtime surface through the W205-W212 local RC closeout package.
- RC closeout runtime for macro coverage audit, deterministic smoke/eval aggregation, source metrics, Hermes live opt-in mapping, public/private security boundary, package/release boundary, and hard-close reporting.
- Public boundary documents for Hermes live opt-in, public/private artifact separation, RC release handling, and W205-W212 hard-close handoff.
- Additional deterministic public tests for live provider/API/MCP/gateway/research/workflow/ontology/skill/security/release boundaries.

### Changed

- Version metadata is aligned to `zeus-agent==0.5.0`.
- README, Hermes comparison, live connection architecture, and platform master docs now describe the `v0.5.0` public source checkpoint.
- Public RC tests no longer depend on private `docs/ai`, `plans`, `harness`, or `evidence` artifacts.

### Notes

- `v0.5.0` is still local-first and deterministic by default.
- Production live execution, real external provider/MCP/gateway/browser/terminal/sandbox operation, tag publication, and GitHub release claims remain gated behind explicit authority, lease, approval, sandbox, evidence, rollback, and release review.
- Private Codex/ULW artifacts, local evidence, local runtime databases, and machine-local operating state remain excluded from the public release.

## v0.4.0 - 2026-06-04

### Added

- Hermes-grade live platform absorption master plan covering CLI, API, gateway, MCP, providers, memory, skills, eval, tracing, recovery, and live runtime parity targets.
- Live agent loop contracts for objective-driven turns, provider/tool coordination, persistence, resilience, and evidence-backed completion.
- Gateway/API runtime scaffolds with session persistence, security review blockers, HTTP server adapters, and G006 scenario/eval coverage.
- Live provider HTTP adapter contracts for OpenAI-compatible style providers with fail-closed request/response handling.
- MCP manager contracts for server registration, tool-surface filtering, provenance checks, and managed runtime decisions.
- Tool sandbox execution contracts for local command mediation, policy checks, path/network controls, and blocked side-effect evidence.
- Research provider and observability gate surfaces for source-backed synthesis, runtime telemetry, evidence logs, and release-quality checks.
- Public master design coverage for MemoryGraph, LLM Wiki, verification-taught learning, ontology-backed knowledge, and adaptive workflow intelligence.

### Changed

- README, Hermes comparison, and live connection architecture now describe the `v0.4.0` public source checkpoint and expanded live-platform absorption scope.
- Public tests now cover Wave 15 through Wave 20 and G006 runtime slices while keeping private Codex harness artifacts out of the repository.
- Version metadata is aligned to `zeus-agent==0.4.0`.

### Notes

- `v0.4.0` remains local-first and deterministic by default.
- The release substantially widens the public implementation surface, but production live execution is still gated behind Zeus authority grants, runtime leases, approvals, sandbox controls, audit evidence, verification, rollback, and release review.
- Private Codex/ULW artifacts, local evidence, local runtime databases, and machine-local operating state remain excluded from the public release.

## v0.3.0 - 2026-06-03

### Added

- Official Zeus Core Language checkpoint with the reduced 12-name product-domain layer mapped to stable technical runtime anchors.
- Public documentation alignment for Zeus Kernel, Athena, Thunderbolt, Aegis, Mercury, Apollo, Hephaestus, Poseidon, Artemis, Demeter, Olympus, and Prometheus.
- Runtime/docs consistency tests that prevent product-domain names from renaming underlying runtime modules.
- Poseidon gateway-boundary guard so it remains gateway/surface containment language instead of sandbox naming.
- High-risk release checkpoint routing for next-wave work, including public/private artifact boundaries and explicit Git publication blocker handling.

### Changed

- README, Hermes comparison, and live connection design now describe the current `v0.3.0` source checkpoint.
- Public evidence language now treats the core-language checkpoint as part of the deterministic local regression surface.
- Release readiness language more clearly separates Hermes-like platform absorption from active live-provider, MCP, gateway, browser, terminal, plugin, network, or remote-sandbox execution.

### Notes

- `v0.3.0` remains local-first and deterministic by default.
- Live integrations remain designed/prepared/dry-run/future until real adapters pass Zeus authority grants, runtime leases, approval receipts, sandbox controls, audit evidence, verification, rollback, and release review.
- Private Codex/ULW artifacts, local evidence, local runtime databases, and machine-local operating state remain excluded from the public release.

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
