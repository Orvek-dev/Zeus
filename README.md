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
  <img alt="Tests" src="https://img.shields.io/badge/tests-1881%20passed-1f883d">
  <img alt="Conformance" src="https://img.shields.io/badge/conformance-88%20scenarios-8250df">
</p>

<p align="center">
  <a href="#zeus">English</a> ·
  <a href="./README.ko.md">한국어</a> ·
  <a href="#why-i-built-zeus">Why I Built Zeus</a> ·
  <a href="#quickstart-10-minutes">Quickstart</a> ·
  <a href="#the-four-gates">The Four Gates</a> ·
  <a href="#docs">Docs</a>
</p>

# Zeus

Zeus is a **local-first governance control plane for AI agents**. It is not
another agent: your agent platform — Claude Code live today; hermes-agent and
OpenClaw adapters contract-frozen, real-host validation pending — keeps doing
the work, and plugs into Zeus through gates. Zeus decides what may run,
records what happened, blocks what must not happen, and converts a clean
track record into fewer interruptions.

```text
host agent (Claude Code / hermes / OpenClaw)
   │ hooks            │ base_url            │ MCP                │ network/fs
   ▼                  ▼                     ▼                    ▼
 Gate 0 hooks    Gate 1 LLM proxy     Gate 2 MCP gateway    Gate 4 egress ring
   └────────────────── decide() → auto | notify | ask | deny ──────────────────┘
                       + receipt + obligations   (Gate 3: /zeus API for remote hooks)
   host executes its own tool → record(receipt, outcome)
   → hash-chained ledger · earned trust · governed-coverage metric
```

One contract carries the whole product: `decide()` is decision-only (Zeus
never executes the host's tool on hook surfaces), and `record()` binds the
host's execution outcome back to the decision receipt.

**The final-action receipt contract.** What the host is told equals what the
ledger says — always. Any condition that can change the final action (an
egress-ring violation, a missing plain-language explanation) is an *input* to
`decide()`, never a post-hoc mutation of its response. A dedicated
conformance suite pins this across every gate, approvals are TTL fail-closed
end to end, and a burned "once" grant is dead for every later process at
every gate.

Around that contract sit the kernel organs:

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
- **Governors** — budget, rate, loop, novelty, and dead-man limits enforced
  before the call, not alerted after it.
- **Flight recorder** — every decision (including DENY) leaves a receipt in a
  hash-chained SQLite ledger; outcomes link back via `caused_by`, so "why did
  this happen" is a chain walk, and governed-coverage is measurable.
- **Graded approvals** — approving is never just yes/no: this once, this
  session, a narrower scope, or reject. Standing grants silence repeat asks;
  hard-risk actions can never be pre-licensed; grant burns persist at every
  gate.
- **Credential broker** — agents plan with secret references and never hold
  raw keys; material is injected only at the egress point, on an allowed
  decision, and the injection itself is recorded as an outcome.

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

## The Four Gates

| Gate | What it does | Status |
| --- | --- | --- |
| **Gate 0 — Claude Code hooks** | PreToolUse → `decide()`, PostToolUse → `record()`. Static tool→capability map; shell commands risk-classified deterministically; approval card with five answers and graded responses. | Live (dogfooding) |
| **Gate 1 — LLM proxy `/v1`** | OpenAI-compatible. Ingress: pre-call budget → HTTP 429, cost attribution per objective, quota-aware model switching (governed). Egress: every `tool_call` decided before release — streamed fragments are buffered whole, denied calls are stripped and replaced with a block notice. Secret-hygiene modes `count / redact / block / ask` with cross-chunk streaming redaction. | Implemented; synthetic conformance |
| **Gate 2 — MCP gateway** | Downstream tools import as quarantined; review activates; a schema rug-pull re-quarantines; injection findings in descriptions or results taint the session; per-tool budgets. | Implemented; synthetic conformance |
| **Gate 3 — zeusd Decision API** | `POST /zeus/decide·record`, `GET /zeus/brief` over the proxy port. HMAC pairing, never zero-confirm. hermes: blocking `pre_tool_call` + attenuated child principals (out-of-envelope subagent = DENY). OpenClaw: exec approval relay with durable, TTL-fail-closed parks. | Implemented; pinned-host validation pending (the v2/v3 gates) |
| **Gate 4 — egress ring** | Host/path ring checked *before* policy — a ring violation is a DENY receipt, not a silent override. Keys injected only at egress on an allowed decision. Emits [sandbox-runtime](https://github.com/anthropics/sandbox-runtime) profiles from the ring. | Ring live in-process; OS-level enforcement via the srt wrapper is the next milestone |

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

**Other hosts** go through the proxy and the `/zeus` API:

```sh
zeus proxy --upstream https://api.openai.com   # /v1 LLM gate + /zeus decision API (loopback by default)
zeus pair --approve ZEUS-XXXX                  # pairing is never zero-confirm
zeus policy --hygiene-mode redact --confirm    # secret hygiene: count | redact | block | ask
```

See [CONNECTING.md](CONNECTING.md) for the Claude Code, hermes-agent, and
OpenClaw walkthroughs. Hosts without any hook surface can call the contract
directly: `zeus decide` reads a `DecisionRequest` JSON and prints the
decision + receipt; `zeus record` binds the outcome. The legacy platform
surface lives under `zeus dev` — see [docs/commands.md](docs/commands.md).

## What Zeus Does

| Layer | What it means |
| --- | --- |
| Decision API v1 | One frozen contract for every gate: `decide()` returns auto/notify/ask/deny plus a receipt and obligations; `record()` binds the host's execution outcome to that receipt. |
| Receipt coherence | The final action returned to the host equals the final receipt in the ledger; boundary violations and explainability are decided *inside* `decide()`, and a conformance suite pins it. |
| Authority envelope | The least-authority compiler turns an objective frame into granted capabilities (tiered), an explicit lock list, budgets, and questions worth asking — and shrinks the next grant to what was actually used. |
| Consequence cards | Ask decisions render five plain-language answers (what / blast radius / reversible / why / precedent). A side-effecting capability with no vetted template cannot resolve to silent auto — and no standing license can cover it. |
| Taint flow | Untrusted and private labels persist per session and trip the lethal-trifecta rules at every decision. |
| Governors | Pre-call budget hard stops (run/objective/fleet), per-capability rate windows, loop caps with no-progress detection, first-seen host/recipient escalation, quiet hours, and a dead-man switch: an unacknowledged weekly digest demotes autonomy. |
| Wallet | Token costs metered per objective in micro-USD; weekly spend digest; over-budget requests refused before the provider is called. |
| Secret hygiene | The proxy scans responses for secret-shaped material: count (default), redact (mask spans, even across stream chunks), block (withhold), ask (park for review) — every mutation leaves its own receipt. |
| Policy packs & NL rules | `zeus policy --apply safe-assistant`, `"weekly budget $12"`-style rules, and mode changes are themselves governed, confirmed, and ledgered. |
| Flight recorder | Hash-chained receipts with causal edges, governed ledger reads (agent view is scoped, masked, audited, and re-tainted), and a coverage metric. |
| Earned autonomy | Real receipts feed per-capability trust; sustained clean records soften risk and shrink scopes; one schema rug-pull re-quarantines an MCP tool. |
| Cognition organs (default-OFF) | Long-term memory writes land as redacted candidates (poisoned candidates store hash + preview only and can never be promoted); skills/plugins install quarantined, hash-pinned, and injection-scanned. |
| Conformance | 88 frozen scenarios across gates 0–4, governance UX, loop governance, both host adapters, hygiene, remote safety, and receipt coherence. Majors are gated on a *pinned real host*: ≥95% plus a 7-day zero-bypass soak with independent out-of-Zeus measurement. |

## Evidence

Measured 2026-06-11 on the public source tree. Read these as deterministic
local regression evidence, not as proof of production readiness.

| Evidence surface | Current result |
| --- | --- |
| Public unit and scenario suite | `1881` tests passed |
| Conformance scenarios | `88` across P3–P13 + receipt coherence |
| Lint | `ruff` clean |
| Package metadata | `zeus-agent==1.0.0a1` (alpha reset; majors are conformance-gated) |
| Raw-secret storage proof | byte-level scan: a proposed memory containing a key never reaches the SQLite file unredacted |

**Honest boundary.** The conformance suite is synthetic: contracts are frozen
against simulated hosts, which is necessary but not sufficient. `v2.0.0`
ships only when a **pinned hermes-agent** passes at ≥95% with a 7-day
real-traffic soak, zero bypasses, measured by instrumentation *outside* Zeus;
`v3.0.0` repeats that for OpenClaw. The egress ring currently decides
in-process and emits sandbox profiles — Zeus does not yet enforce at the OS
layer (that is the next milestone, and the only real defense against a
non-cooperative host). `/v1` binds loopback by default; non-loopback binds
refuse to start without issued tokens (`zeus pair --issue-v1-token`, with TTL
and revocation) or an explicit unsafe flag. Cognition organs are default-OFF.
No hosted SaaS, browser automation, or third-party production validation is
claimed.

## Docs

| Document | Purpose |
| --- | --- |
| [한국어 README](README.ko.md) | Korean overview, reason for Zeus, quickstart, and document guide |
| [Connecting hosts](CONNECTING.md) | Plug Claude Code, hermes-agent, or OpenClaw into the gates |
| [Commands](docs/commands.md) | Legacy CLI command catalog, now reachable under `zeus dev` |
| [Docker And OrbStack](docs/docker.md) | Local Docker/OrbStack build, run, smoke-check, and volume instructions |
| [Security policy](SECURITY.md) | Public security posture and the current alpha boundary |
| [Changelog](CHANGELOG.md) | Release history, including the pre-refoundation line |

## License

Zeus is released under the MIT License. See [LICENSE](LICENSE).
