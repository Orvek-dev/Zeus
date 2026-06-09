<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/zeus-symbol-transparent-white-tight.png">
    <source media="(prefers-color-scheme: light)" srcset="./assets/zeus-symbol-transparent-black-tight.png">
    <img src="./assets/zeus-symbol-transparent-black-tight.png" width="360" alt="Zeus: goal-oriented AI agent" />
  </picture>
</p>

<p align="center">
  <a href="https://github.com/Orvek-dev/Zeus/releases/tag/v4.1.0"><img alt="Version" src="https://img.shields.io/badge/version-4.1.0-2ea44f"></a>
  <a href="./LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-0969da"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776ab">
  <img alt="Local first" src="https://img.shields.io/badge/local--first-runtime-6f42c1">
  <img alt="Tests" src="https://img.shields.io/badge/tests-1480%20passed-1f883d">
  <img alt="Hermes inspired" src="https://img.shields.io/badge/Hermes--inspired-governed%20runtime-8250df">
</p>

<p align="center">
  <a href="#zeus-agent">English</a> ·
  <a href="./README.ko.md">한국어</a> ·
  <a href="#why-i-built-zeus">Why I Built Zeus</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#docs">Docs</a>
</p>

# Zeus Agent

Zeus is a goal-oriented AI agent runtime for governed work. It is built around
a simple premise: an agent should not merely sound capable or keep acting. It
should understand the user's objective, operate within controlled authority,
record what it did, and prove completion with evidence.

```text
Hermes-style breadth = providers + tools + sessions + gateway + MCP + skills
Zeus control model  = objective contracts + authority gates + evidence + promotion review
```

Zeus is inspired by the platform breadth of Hermes, but it keeps a different
center of gravity. The public `v4.1.0` release is a local-first, governed
platform boundary: goal intelligence, cognitive-provider activation,
productized platform status, ObjectiveRun start/status/export, provider/MCP/tool/gateway/runtime contracts,
memory and ontology surfaces, self-evolution review queues, and release-gated
evidence checks. Live provider, MCP, web, gateway, browser, plugin, and network
execution remains designed/prepared/dry-run/future unless a later release wires
it through authority, leases, approval, sandboxing, evidence, and promotion.

## Why I Built Zeus

I did not build Zeus because I wanted another smart, general-purpose AI agent.

As AI agents become more capable, the work of checking whether they are
actually doing the right thing has also grown. An agent may sound confident,
run tools, generate plans, and keep moving, but the user still has to ask:
What did it do? Why did it do that? Was it allowed to do that? Did it satisfy
the original goal? Can I trace the result back to evidence?

I think that is the real problem.

My ideal agent is not just broad, self-improving, or intelligent. It should
understand the user's objective precisely, operate inside controlled authority
and safety rules, record what it did, expose why it made each decision, and
prove its work with evidence.

Zeus is built around that idea.

The goal is not to make an agent that merely keeps acting. The goal is to make
an agent that can pursue a user's objective while remaining inspectable,
governable, and accountable. If the agent cannot show what happened, what
authority it used, what evidence it collected, and why the work should be
considered complete, then it should not pretend that the job is done.

## Quickstart

Run this from a fresh clone with Python 3.10 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m pytest -q
```

Try the product-facing local surfaces:

```sh
zeus kernel-status
zeus productized-platform --scenario status --json
zeus cognitive-provider-activation --scenario fake-provider-intent --objective "Zeus, turn my goal into a governed workflow." --json
zeus goal-intelligence-runtime --scenario understand-objective --objective "Build a research backed coding workflow with parallel workers." --task-count 6 --requires-code --requires-research --json
zeus objective-start --objective "Zeus, turn my goal into an evidence-backed run." --acceptance-criterion objective-run-created --json
zeus release-gated-ulw --target-version v4.1.0 --json
```

For the longer command catalog, see [docs/commands.md](docs/commands.md).

## What Zeus Does

Zeus turns open-ended work into inspectable execution.

| Layer | What it means |
| --- | --- |
| Objective contract | The user's goal is normalized into acceptance criteria, assumptions, unknowns, and evidence obligations. |
| Objective run | A started objective becomes a persisted local run with start/status/export surfaces and evidence-based completion arbitration. |
| Authority gate | Capabilities, paths, credentials, tools, and live surfaces must be explicitly allowed before execution. |
| Runtime lease | Live-capable work is scoped, temporary, and tied to approval, sandbox, credential, and audit requirements. |
| Evidence record | Completion is based on observable artifacts, receipts, tests, traces, and reviewable output, not confident language. |
| Promotion review | Memory, ontology, workflow patterns, skills, and rules stay candidate-only until reviewed and promoted. |
| Public boundary | Zeus reports what is ready, what is blocked, and what remains dry-run or future instead of overstating production-live readiness. |

## Zeus Core Language

The Zeus core language has exactly these 12 product-domain pillars. The
technical runtime identifiers are preserved, and product-domain labels do not
rename runtime modules.

| Product name | Technical anchor |
| --- | --- |
| Zeus Kernel | `objective_runtime`, `verification_runtime`, and evidence/authority center |
| Athena | `objective_runtime` |
| Thunderbolt | `runtime_lease` |
| Aegis | `security_runtime`, lease, and sandbox policy |
| Mercury | `transport_runtime`, `connector_runtime`, and MCP/API/gateway routing |
| Apollo | `model_runtime`, `provider_runtime`, and eval boundaries |
| Hephaestus | `tool_runtime` |
| Poseidon | `gateway_runtime` |
| Artemis | `research_runtime` |
| Demeter | `ontology_runtime` and durable state |
| Olympus | `orchestration_runtime` and work-loop coordination |
| Prometheus | `skill_evolution` |

Hermes remains upstream/reference only. Mercury is the Zeus internal transport product name.

## Evidence

The latest public-safe local evidence snapshot was measured on 2026-06-09.
Read these numbers as deterministic local regression evidence for the public
source release, not as proof of broad production readiness.

| Evidence surface | Current result |
| --- | --- |
| Public unit and scenario suite | `1480` public tests passed |
| Final architecture eval | `10/10` checks passed |
| Total architecture eval | `9/9` checks passed |
| Package build | sdist and wheel build for `zeus-agent==4.1.0` passed |
| Public safety boundary | Local Codex control packs, private notes, evidence logs, runtime DBs, and machine-local artifacts excluded |

The release does not claim hosted SaaS readiness, production external provider
execution, production MCP catalogs, unattended gateway operations, browser or
terminal automation, remote sandbox hard isolation, or third-party production
validation. Those claims remain blocked until live integrations are wired
through the authority, lease, evidence, and rollback contracts.

## Docs

| Document | Purpose |
| --- | --- |
| [한국어 README](README.ko.md) | Korean overview, reason for Zeus, quickstart, and document guide |
| [Commands](docs/commands.md) | Practical CLI command catalog for the public local surfaces |
| [Hermes comparison](docs/hermes-comparison.md) | Hermes baseline architecture, Zeus architecture, and why Zeus keeps a governed kernel/runtime split |
| [Live connection architecture](docs/live-connection-architecture.md) | Target design for real AI API, MCP, tool, gateway, web, browser, terminal, and sandbox connections |
| [Hermes-grade platform master design](docs/hermes-grade-platform-master-design.md) | Long-form target product, UX, architecture, security, and roadmap contract |
| [Hermes live platform absorption master plan](docs/hermes-live-platform-absorption-master-plan.md) | Full-scale future absorption plan for Hermes-like live platform breadth |
| [Security policy](SECURITY.md) | Public security posture and current governed live boundary |
| [Changelog](CHANGELOG.md) | Release history and public-safe notes |

## License

Zeus is released under the MIT License. See [LICENSE](LICENSE).
