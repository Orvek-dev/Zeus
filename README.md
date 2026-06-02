# Zeus Agent

Zeus is a governed AI agent runtime for objective-oriented work.

It is designed to absorb Hermes-style general agent platform capabilities while keeping Zeus's own control model: objectives are compiled into explicit contracts, capabilities are gated by authority, tool and model calls are mediated by runtime boundaries, and completion requires evidence instead of a loose chat transcript.

Current release: `v1.0.0`

## What Zeus Provides

- Objective compiler for turning a flexible user goal into a bounded runtime contract.
- Capability broker with explicit authority, path grants, side-effect labels, and fail-closed dispatch.
- Agent work loop scaffolding for local plan execution and evidence capture.
- Provider runtime interfaces for fake, local LLM, OpenAI-compatible, and Anthropic metadata-oriented providers.
- Tool runtime registry with schema visibility and dispatch controls.
- Connector lifecycle and execution contracts for externally backed integrations.
- Transport registry and persistent SQLite-backed transport state for local runtime checks.
- Runtime lease and promotion controls so dry-run, local, and live-capable paths are separable.
- Skill-evolution proposal queue modeled after validation-gated self-improvement.
- CLI eval commands that exercise kernel, runtime, provider, tool, transport, conversation, production scaffold, and final architecture surfaces.

Zeus is not presented as an unconstrained autonomous agent. The public `v1.0.0` package is a governed runtime foundation with deterministic local scenarios and contract tests. Live provider, MCP, gateway, browser, terminal, and remote execution should be wired through the same authority and evidence boundaries instead of bypassing them.

## Architecture

```text
User objective
  -> Objective compiler
  -> Governed runtime contract
  -> Work loop plan
  -> Provider, tool, connector, transport, and workflow runtimes
  -> Evidence and verification runtime
  -> Promotion decision
```

The important boundary is that the agent layer does not own every runtime concern. Zeus keeps a kernel/runtime split:

- Kernel: authority, capability graph, broker decisions, evidence records, and completion checks.
- Agent runtime: prompt shaping, loop lineage, compression, conversation surfaces, and run orchestration.
- Model runtime: provider selection, request/response contracts, local and API-compatible provider adapters.
- Tool runtime: tool schema registry, visibility filtering, and dispatch constraints.
- Connector runtime: lifecycle records and execution outcomes for external systems.
- Transport runtime: local/remote transport manifests, registry gates, and persistent state.
- Workflow and gateway runtime: scheduled jobs, gateway drafts, and local gateway scaffolds.
- Verification runtime: objective evidence, artifact validation, and promotion readiness.
- Skill evolution: proposed improvements that must pass validation before promotion.

This shape lets Zeus be both purpose-oriented and general-purpose. A user can ask for flexible work, but the runtime still knows what authority was granted, which tools were visible, which providers were selected, what side effects were allowed, and why completion or promotion was accepted or blocked.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Zeus requires Python `3.10` or newer.

## CLI

```bash
zeus --help
zeus kernel-status
zeus kernel-dump --scenario approved-read --json
zeus wave2-loop --scenario happy --json
zeus final-core --objective "Build a governed research agent" --json
zeus final-eval --json
```

The CLI exposes local deterministic scenarios for the current runtime layers. These commands are useful for contract validation, architecture checks, and regression tests before connecting live external systems.

## Development

```bash
python -m pytest -q
python -m compileall -q src tests
python -m zeus_agent final-eval --json
```

The public repository intentionally excludes local Codex harness packs, private planning notes, evidence logs, runtime databases, and other machine-local artifacts. Public source should stay focused on reusable Zeus runtime code, tests, release notes, and CI.

## Release

`v1.0.0` is the first public Zeus Agent release. It establishes the governed runtime foundation and public packaging baseline.

See [CHANGELOG.md](CHANGELOG.md) for release notes.

## License

Zeus is released under the MIT License. See [LICENSE](LICENSE).
