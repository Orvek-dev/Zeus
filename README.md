<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/zeus-symbol-transparent-white-tight.png">
    <source media="(prefers-color-scheme: light)" srcset="./assets/zeus-symbol-transparent-black-tight.png">
    <img src="./assets/zeus-symbol-transparent-black-tight.png" width="360" alt="Zeus: governance control plane for AI agents" />
  </picture>
</p>

<p align="center">
  <a href="https://github.com/Orvek-dev/Zeus/releases"><img alt="Version" src="https://img.shields.io/badge/version-1.0.0--alpha.1-2ea44f"></a>
  <a href="./LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-0969da"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776ab">
  <img alt="Local first" src="https://img.shields.io/badge/local--first-control%20plane-6f42c1">
  <img alt="Tests" src="https://img.shields.io/badge/tests-1791%20passed-1f883d">
  <img alt="Conformance" src="https://img.shields.io/badge/conformance-12%2F12%20starter-8250df">
</p>

<p align="center">
  <a href="#zeus">English</a> ·
  <a href="./README.ko.md">한국어</a> ·
  <a href="#why-i-built-zeus">Why I Built Zeus</a> ·
  <a href="#quickstart-10-minutes">Quickstart</a> ·
  <a href="#docs">Docs</a>
</p>

# Zeus

Zeus is a **local-first governance control plane for AI agents**. It is not
another agent: your agent platform — Claude Code today, hermes-agent and
OpenClaw planned — keeps doing the work, and plugs into Zeus through gates.
Zeus decides what may run, records what happened, and converts a clean track
record into fewer interruptions.

```text
host agent (Claude Code / hermes / OpenClaw)
      │  every tool call, before it runs
      ▼
Zeus decide(principal, capability, args, context)
      → auto | notify | ask | deny  + receipt + obligations
      ▼
host executes its own tool → record(receipt, outcome)
      → hash-chained ledger · earned trust · coverage metric
```

One contract carries the whole product: `decide()` is decision-only (Zeus
never executes the host's tool on hook surfaces), and `record()` binds the
host's execution outcome back to the decision receipt. Around that contract
sit the kernel organs:

- **Least-authority compiler** — an objective is compiled into an
  `AuthorityEnvelope`: granted capabilities with tiers and scopes (auto /
  ask-first / always-ask), an explicit lock list of adjacent-dangerous
  capabilities that were never derived from the objective, a budget, and
  VoI-ranked questions. Anything that does not trace to the objective is
  excluded — opportunistic scope is structurally impossible.
- **Taint engine** — sessions carry information-flow labels (untrusted /
  private). Untrusted data reaching an external sink forces a question;
  private data heading to an unapproved host is denied outright; an agent
  reading its own ledger re-taints the session (anti-Goodhart).
- **Governors** — budget, rate, and loop limits enforced before the call,
  not alerted after it.
- **Flight recorder** — every decision (including DENY) leaves a receipt in a
  hash-chained SQLite ledger; outcomes link back via `caused_by`, so "why did
  this happen" is a chain walk, and governed-coverage is measurable.
- **Graded approvals** — approving is never just yes/no: this once, this
  session, a narrower scope, or reject. Standing grants silence repeat asks;
  hard-risk actions can never be pre-licensed.
- **Credential broker** — agents plan with `secret-proof://` references and
  never hold raw keys; sealed material is released only at the egress point,
  on an allowed decision, for an approved host.

The north-star metric is **asks per week**: governance that earns autonomy
down, instead of nagging forever or rubber-stamping everything.

## Why I Built Zeus

I did not build Zeus because I wanted another smart, general-purpose AI agent.

As AI agents become more capable, the work of checking whether they are
actually doing the right thing has also grown. An agent may sound confident,
run tools, generate plans, and keep moving, but the user still has to ask:
What did it do? Why did it do that? Was it allowed to do that? Did it satisfy
the original goal? Can I trace the result back to evidence?

I think that is the real problem — and it is a control-plane problem, not an
agent problem. The agents keep getting better on their own. What is missing
is the layer that holds authority, budgets, information flow, and evidence
constant no matter which agent is doing the work. The stronger the host
platforms get, the more that layer matters.

So Zeus is built as that layer. If the agent cannot show what happened, what
authority it used, what evidence it collected, and why the work should be
considered complete, then it should not pretend that the job is done.

## Quickstart (10 minutes)

From a fresh clone with Python 3.10+:

```sh
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
```

**1. Initialize the local control plane** (~/.zeus/control-plane: ledger,
trust counts, grants, session taint):

```sh
zeus init
```

**2. Connect your first gate — Claude Code hooks.** From your project
directory:

```sh
zeus connect claude-code --write   # merges PreToolUse/PostToolUse hooks into .claude/settings.json
```

**3. Work normally in Claude Code.** Reads run silently; the first file edit
or risky command surfaces an approval card with five answers — what, blast
radius, reversibility, why, precedent — instead of a naked yes/no.

**4. Stop answering the same question twice.** License what you trust:

```sh
zeus approve fs.write --scope session --session-id <session>   # this session
zeus approve fs.write --scope narrower --path /work/project    # this path, standing
```

**5. Inspect what your agent actually did:**

```sh
zeus status                    # decision mix, asks, governed coverage, chain integrity
zeus ledger --tail 20          # recent receipts
zeus ledger --why trust.ev.000042   # the causal chain behind one action
```

Hosts without a hook surface can call the contract directly: `zeus decide`
reads a `DecisionRequest` JSON and prints the decision + receipt; `zeus
record` binds the outcome. The full legacy platform surface (and the demoted
objective-run executor, now a conformance harness) lives under `zeus dev` —
see [docs/commands.md](docs/commands.md), prefixing each command with `dev`.

## What Zeus Does

| Layer | What it means |
| --- | --- |
| Decision API v1 | One frozen contract for every gate: `decide()` returns auto/notify/ask/deny plus a receipt and obligations; `record()` binds the host's execution outcome to that receipt. |
| Authority envelope | The least-authority compiler turns an objective frame into granted capabilities (tiered), an explicit lock list, budgets, and questions worth asking — and shrinks the next grant to what was actually used. |
| Gate 0: Claude Code hooks | PreToolUse → decide, PostToolUse → record. A static tool→capability map; shell commands are risk-classified deterministically before they are judged. |
| Approval card | Ask decisions render five answers (what / blast radius / reversible / why / precedent) with graded responses: once, this session, narrower, reject. No plain-language template → no silent auto. |
| Taint flow | Untrusted and private labels persist per session and trip the lethal-trifecta rules at every decision. |
| Governors | Pre-call budget hard stops (run/objective/fleet), per-capability rate windows, loop iteration caps with no-progress detection. |
| Flight recorder | Hash-chained receipts with causal edges, governed ledger reads (agent view is scoped, masked, audited, and re-tainted), and a coverage metric. |
| Earned autonomy | Real receipts feed per-capability trust; sustained clean records soften risk and shrink scopes; one schema rug-pull re-quarantines an MCP tool. |
| Conformance | A pinned per-host scenario suite (12 starter, scaling to ~40) is the only path to a major version: ≥95% plus a 7-day zero-bypass soak. |
| Public boundary | Zeus reports what is governed, what is bypassed, and what remains designed/prepared/dry-run/future instead of overstating readiness. |

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

The latest public-safe local evidence snapshot was measured on 2026-06-11.
Read these numbers as deterministic local regression evidence for the public
source release, not as proof of broad production readiness.

| Evidence surface | Current result |
| --- | --- |
| Public unit and scenario suite | `1791` public tests passed |
| Conformance starter suite | `12/12` governed scenarios passed |
| Final architecture eval | `10/10` checks passed |
| Total architecture eval | `9/9` checks passed |
| Package metadata | `zeus-agent==1.0.0a1` (alpha reset; majors are conformance-gated) |
| Public safety boundary | Local control packs, private notes, evidence logs, runtime DBs, and machine-local artifacts excluded |

The alpha does not claim hosted SaaS readiness, production external provider
execution, production MCP catalogs, unattended gateway operations, browser or
terminal automation, remote sandbox hard isolation, or third-party production
validation. A `v2.0.0` only ships when one real host integration passes the
pinned conformance suite at ≥95% with a 7-day real-traffic soak and zero
bypasses; until each surface is retrofitted and evidenced, those surfaces
remain designed/prepared/dry-run/future rather than active production-live
execution.

## Docs

| Document | Purpose |
| --- | --- |
| [한국어 README](README.ko.md) | Korean overview, reason for Zeus, quickstart, and document guide |
| [Commands](docs/commands.md) | Legacy CLI command catalog, now reachable under `zeus dev` |
| [Docker And OrbStack](docs/docker.md) | Local Docker/OrbStack build, run, smoke-check, and volume instructions |
| [Hermes comparison](docs/hermes-comparison.md) | Hermes baseline architecture, Zeus architecture, and why Zeus keeps a governed kernel/runtime split |
| [Live connection architecture](docs/live-connection-architecture.md) | Target design for real AI API, MCP, tool, gateway, web, browser, terminal, and sandbox connections |
| [Hermes-grade platform master design](docs/hermes-grade-platform-master-design.md) | Long-form target product, UX, architecture, security, and roadmap contract |
| [Hermes live platform absorption master plan](docs/hermes-live-platform-absorption-master-plan.md) | Full-scale future absorption plan for Hermes-like live platform breadth |
| [Security policy](SECURITY.md) | Public security posture and current governed live boundary |
| [Changelog](CHANGELOG.md) | Release history, including the pre-refoundation line |

## License

Zeus is released under the MIT License. See [LICENSE](LICENSE).
