# Changelog

All notable changes to Zeus Agent are recorded here.

## Unreleased

## v1.0.0-alpha.9 - 2026-06-13

### Fixed

- Aligned the OpenClaw approval relay with the live
  `exec.approval.requested` event shape by reading nested request payloads,
  deriving session keys from real OpenClaw fields, and resolving through
  `exec.approval.resolve` with `allow-once` / `deny` decisions.
- Preserved the legacy relay emission fields while adding OpenClaw-compatible
  `method`, `params`, and `decision` fields so older tests and newer pinned
  host transports can both consume the resolution event.

### Evidence

- `.venv/bin/python -m pytest -q` passed: `299` tests.
- `ruff` clean.
- `.venv/bin/pip install -e . --no-deps` succeeded, `zeus-agent 1.0.0a9`
  reported through the installed console script, and `zeus status` passed on a
  fresh smoke home.
- Private live-host evidence stayed local-only: OpenClaw O4/O5 approval-cycle
  dogfood passed with a separately connected approval observer, and Hermes
  one-iteration soak rehearsal passed.

## v1.0.0-alpha.8 - 2026-06-13

### Added

- Added a minimal `zeus tui` control tower surface for the approval loop:
  current decision mix, pending parked actions, active grants, replay approvals,
  chain health, and one-shot approval actions from the operator side.
- Added remembered parked approvals with `zeus approve --parked ... --remember`
  and bounded `--hours` expiry, while preserving one-shot replay approval for
  the default path.
- Added an OpenClaw relay bridge that can flush externally resolved parked
  approvals back to an OpenClaw host transport through
  `exec.approval.resolve`.

### Fixed

- Split parked approval resolution out of command parsing so CLI, TUI, and
  future cockpit surfaces use the same approval effect.
- Blocked remembered grants for hard-risk parked actions and kept invalid
  narrowed-path approvals from consuming pending actions.

### Evidence

- `.venv/bin/python -m pytest -q` passed: `298` tests.
- `ruff` clean.
- `.venv/bin/pip install -e . --no-deps` succeeded and
  `zeus-agent 1.0.0a8` reported through the installed console script.
- Private live-host evidence stayed local-only: Hermes hard-egress + segmented
  + TUI rehearsal passed, and OpenClaw `openclaw@2026.6.6` pin smoke resolved
  to upstream commit `8c802aa`.

## v1.0.0-alpha.7 - 2026-06-13

### Fixed

- Reduced a Hermes dogfood false positive by treating `python -m hermes --help`
  and `python -m hermes_agent --help` as read-only module probes instead of
  high-risk unknown execution.
- Serialized append-only evidence ledger writes with `BEGIN IMMEDIATE`,
  connection busy timeouts, and schema-initialization retry logic so concurrent
  exact-payload replay checks cannot race on `seq` or `prev_hash`.

### Evidence

- `.venv/bin/python -m pytest` passed: `292` tests.
- `ruff` clean.
- Hermes R13 segmented dogfood on the final tree: `21/21` pass,
  host-tool fall-through `0`, proxy secret findings `0`, and `chain_ok=true`
  for all cases. OpenClaw remains blocked on a real pinned host before any
  95% control claim.

## v1.0.0-alpha.6 - 2026-06-13

### Fixed

- Added Hermes-aware `memory` mapping at the LLM proxy boundary so host memory
  reads no longer fall through to conservative `host.tool.*`, and memory writes
  are parked as `agent.memory.write` with only a stable content hash in
  receipts.
- Preserved more Hermes tool evidence by extracting filesystem paths from
  path-like search/query fields and network hosts from `url`, `urls`, and
  URL-shaped query arguments.
- Tightened dogfood command classification for real Hermes probes: read-only
  `python -m pip` metadata commands, Zeus module help probes, and fd redirects
  stay low-risk, while `python -m compileall` is classified as a local write
  instead of an external high-risk action.
- Hardened exact-payload replay approval under concurrent retries so a parked
  approval can be consumed once, not twice.

### Changed

- R12 segmented live dogfood now runs each Hermes case against an isolated Zeus
  home and proxy port, with per-case `/tmp` artifact cleanup and criteria-aware
  reporting.

### Evidence

- `.venv/bin/python -m pytest -q` passed: `291` tests.
- `ruff` clean.
- Live-host eval schema verifier passed for Hermes, Claude Code, and OpenClaw.
- Hermes R12 segmented dogfood on the final tree: `13/20` pass, memory
  fall-through `0`, proxy secret findings `0`, and `chain_ok=true` for all
  cases. Remaining incomplete cases are tracked as live prompt/fixture gaps,
  not as evidence of successful bypass.

## v1.0.0-alpha.5 - 2026-06-12

### Changed

- Moved the pre-control-plane wave, objective, G006, and RC closeout harnesses
  into `attic/legacy-wave`; the product source tree now has zero active
  `*wave*.py` modules.
- Narrowed the default public release evidence to the product suite only:
  `tests/core` plus `tests/conformance`, currently `283` tests.
- Removed the legacy command catalog from public docs and replaced `zeus dev`
  with an archived-harness notice.
- Renamed the active loopback HTTP helper from the old wave name to
  `loopback_provider_http_server`.

### Fixed

- `python -m zeus_agent` now opens the product CLI entrypoint.
- `zeus approve fs.write` now defaults to a current-directory narrowed grant
  instead of requiring a session id for the common dogfood approval path.

### Evidence

- `.venv/bin/python -m pytest` passed: `283` tests.
- `ruff` clean.
- `git diff --check` clean.
- `.venv/bin/pip install -e . --no-deps` succeeded.
- CLI smoke passed for `zeus --version`, `python -m zeus_agent --version`,
  `zeus dev kernel-status`, `zeus init`, `zeus status`, `zeus approve
  fs.write`, and `zeus approvals`.

## v1.0.0-alpha.4 - 2026-06-12

### Added

- Added top-tier self-protection for Zeus control-plane material, plus a
  tripwire command for out-of-band control-plane file changes.
- Added `zeus connect hermes --check` canary receipt verification.
- Added a minimum completion gate for claimed-done Stop/post-task hooks:
  claimed artifacts and test commands must have evidence.
- Added operator-inbox cards with short parked IDs, `zeus approve --last`,
  `zeus notify --webhook`, `zeus freeze`, latency budget measurement, and
  Claude Code permission-import summaries that exclude raw secret material.
- Stamped schema versions on the control-plane state store and evidence ledger.

### Changed

- Split the product CLI command registry out of `cli_main.py` into
  focused `cli_runtime/*_commands.py` modules; `cli_main.py` is now a thin
  Typer entrypoint and the boundary is locked by a product-surface test.
- Updated README/README.ko to match the current product surface: Hermes
  dogfood onboarding, operator inbox, completion gate, self-protection,
  tripwire, latency checks, and the public/private dogfood boundary.
- Aligned package metadata to `zeus-agent==1.0.0a4`.

### Evidence

- Product test suite passed without private live-host eval files:
  `.venv/bin/python -m pytest --ignore=tests/test_live_host_eval_tree.py`
  passed: `1927` tests.
- `ruff` clean.
- `git diff --check` clean.
- `zeus status --home /tmp/zeus-a4-baseline-smoke` returned
  `chain_ok=true`.
- Private dogfood/eval assets remain local-only and ignored:
  `evals/`, `tests/test_live_host_eval_tree.py`.

## v1.0.0-alpha.3 - 2026-06-12

### Fixed

- Treat sensitive filesystem reads as governed actions: `.env`, private-key,
  cloud credential, SSH, and secret-like paths now force an ASK before content
  can be exposed through `fs.read`.
- Extended Hermes and proxy tool mapping for web aliases such as
  `web_extract`, `fetch_url`, `extract_url`, and `browser_navigate` so they
  resolve to `web.fetch` instead of falling through to conservative
  `host.tool.*`.
- Reduced dogfood false positives for read-only diagnostics: path-qualified
  Python binaries, versioned `python3.x`, safe `python -m pip` read-only
  commands, and Zeus module probes now classify as read-only when appropriate.

### Added

- `zeus status` now separates standing grants, replay authorizations, approval
  queue state, and the operator inbox so active authority is not confused with
  resolved approval history.
- Replay authorization rows are queryable from the control-plane store for
  status and cockpit surfaces.

### Evidence

- `ruff` clean.
- Product test suite passed without private live-host eval files:
  `.venv/bin/python -m pytest --ignore=tests/test_live_host_eval_tree.py`
  passed: `1915` tests.
- Existing Hermes dogfood status smoke on `dogfood-r5b`: observed `25`,
  governed `25`, `chain_ok=true`, pending approvals `0`; new status fields
  rendered `grant_inventory`, `approval_queue`, and `operator_inbox`.

## v1.0.0-alpha.2 - 2026-06-12

### Fixed

- Preserved receipt/action coherence on the OpenAI-compatible streaming proxy:
  upstream failures now surface before success headers are emitted, malformed
  empty streams fail closed, and stream failures are recorded as failures.
- Made Hermes proxy gating host-aware so Hermes tool calls use the Hermes
  capability catalog before falling back to conservative `host.tool.*` mapping.
- Added a parked-ASK operator handoff: pending actions are inspectable,
  approvable once by payload, and replayed without granting standing high-risk
  authority.
- Reduced ASK spirals by deduplicating pending parks and counting only
  released decisions toward the loop governor.
- Tightened command-risk classification for dogfood diagnostics: read-only git
  probes, Python module/version probes, shell builtins, and `/dev/null` sinks
  no longer escalate as writes while destructive compound commands stay
  fail-closed.
- Improved Hermes operator UX and observability with shell-hook-compatible
  connect output, hook checks, cleaner approval guidance, grant status
  reporting, and precise `zeus why --parked` timelines.

### Evidence

- `ruff` clean.
- `.venv/bin/python -m pytest` passed: `1911` tests.
- Clean Hermes dogfood home `dogfood-clean-r3`: observed `37`, governed `37`,
  `chain_ok=true`, pending approvals `[]`, secret findings `0`; write approval
  replay succeeded and destructive delete remained blocked.

## v1.0.0-alpha.1 - 2026-06-11

### Refoundation

Zeus is re-founded as a **local-first governance control plane** that external
agent platforms (Claude Code today; hermes-agent and OpenClaw planned) plug
into through gates. Versioning is reset to `v1.0.0-alpha.N`: from here, a
MAJOR version is only earned when one host integration passes a pinned
conformance suite at ≥95% plus a 7-day real-traffic soak with zero bypasses.

### Added

- **Decision API v1** (`decision_api_runtime`): the frozen two-endpoint
  contract — `decide(DecisionRequest) → DecisionResponse` (decision-only, a
  receipt for every decision including DENY) and `record(receipt_id,
  ExecutionOutcome)` (host executes, Zeus records). Decision/execution split:
  on hook surfaces Zeus never executes the host's tool.
- **Least-authority compiler** (`authority_compiler_runtime`): objective frame
  → `AuthorityEnvelope` via capability resolution, dependency-closure
  provenance (untraced capability requests are excluded — opportunistic scope
  is structurally impossible), per-capability tiers (auto / ask_first /
  always_ask), an EXPLICIT lock list of adjacent-dangerous siblings, taint
  overlay, VoI-thresholded questions, burn-after-use and usage-based shrink,
  and subagent attenuation via `derive_for_child`.
- **Taint / information-flow engine** (`taint_runtime`): session labels
  (untrusted / private / public) with provenance, lethal-trifecta predicates
  (untrusted→external-sink forces ASK; private→unapproved-host DENIES;
  credential+send escalates one tier), and the anti-Goodhart rule that an
  agent's own ledger reads re-taint the session.
- **Governors** (`governor_runtime`): pre-call budget hard stops (run /
  objective / fleet scopes → DENY), sliding-window rate limits (→ ASK), and
  loop iteration caps with state-hash no-progress detection (→ ASK).
- **Flight recorder** (`trust_loop_runtime.flight_recorder`): new ledger kinds
  (`execution_outcome`, `rollback_receipt`, `gate_observation`,
  `ledger_read`), `caused_by` causal edges with a `why()` chain walker, and a
  governed-coverage metric.
- **Governed ledger access** (`trust_loop_runtime.ledger_access`): console
  principals read everything; agent principals read only their own session,
  masked of policy internals, with the read itself appended to the ledger and
  the returned data tagged untrusted.
- **Credential broker vault** (`credential_broker_runtime`):
  `secret-proof://<scope>` refs resolve through a vault backend (env-var
  default) and release sealed credentials at the egress point only, on an
  allowed decision for an approved host — never to the agent.
- **Gate 0 — Claude Code hooks** (`adapters/claude_code_hook`): PreToolUse →
  `decide()` with a static tool→capability map (Bash routed by deterministic
  command-risk classification), PostToolUse → `record()`, persisted session
  taint and standing grants, gate observations for the coverage metric, and
  **approval card v1** (what / blast radius / reversible / why / precedent +
  graded once/session/narrower/reject answers). A side-effecting action with
  no plain-language template auto-escalates to ASK.
- **Product CLI** (`zeus`): init · connect · hook · decide · record · approve ·
  approvals · ledger · status, with the entire legacy platform surface and the
  demoted executor parked under `zeus dev`.
- **ACS-manifest read compatibility** (`acs_compat_runtime`): a thin loader
  mapping external agent-capability-spec interception points onto Zeus
  capability ids.
- **Conformance starter suite**: the first 12 governed scenarios that seed the
  ~40-scenario per-host suite gating future major versions.
- `THIRD_PARTY_NOTICES.md`.

### Added — the four gates and hardening (same alpha, public push)

- **Gate 1 — LLM proxy** (`proxy_runtime`, `wallet_runtime`): OpenAI-compatible
  `/v1` server. Ingress budget enforcement (429 before the provider is
  called), per-objective micro-USD cost attribution, governed quota-aware
  model switching, hang watchdog. Egress tool_call interception: streamed
  fragments buffered whole, denied calls stripped and replaced with a block
  notice so the model re-plans; oversized buffers fail closed. Secret-hygiene
  policy modes `count | redact | block | ask` — redact masks spans even
  across SSE chunk boundaries (rolling window); block/ask buffer the whole
  stream (bounded, overflow fails closed) and withhold/park on findings;
  every body mutation leaves its own receipt.
- **Gate 2 — MCP gateway** (`mcp_gateway_runtime`): downstream tools import as
  quarantined, review activates, schema rug-pull re-quarantines, injection
  findings in descriptions or results taint the session, per-tool budgets.
- **Gate 3 — zeusd Decision API** (`zeusd_runtime`, `pairing_runtime`):
  `POST /zeus/decide·record` + `GET /zeus/brief` over the proxy port, HMAC
  pairing (never zero-confirm). **hermes adapter**: blocking `pre_tool_call`
  gate with attenuated child principals — an out-of-envelope subagent is
  DENIED. **OpenClaw adapter**: exec approval relay (allow/deny immediately,
  dangerous commands park until the operator answers) with a durable
  parked→request mapping that survives relay restarts.
- **Gate 4 — egress ring** (`egress_runtime`): host/path ring checked BEFORE
  policy — a ring violation enters `decide()` as a boundary violation and
  becomes a truthful DENY receipt. Key-only-at-egress credential injection,
  recorded as an outcome. Emits sandbox-runtime (srt) profiles from the ring.
- **Final-action receipt contract (P11)**: the invariant "the final action
  returned to the host equals the final receipt in the ledger", enforced
  inside `decide()` (boundary-violation short-circuit + injected
  explainability step — an unexplainable side-effecting action can neither
  run silently nor be covered by a standing license). Post-hoc gate mutations
  deleted; pinned by a dedicated receipt-coherence conformance suite plus a
  template-coverage invariant.
- **Governance UX** (`consequence_runtime`, `policy_pack_runtime`,
  `digest_runtime`, `nl_policy_runtime`): Korean plain-language consequence
  cards; signed policy packs and NL rules where the policy change itself is
  governed and ledgered; weekly digest with license meter and a dead-man
  switch (an unacknowledged digest demotes autonomy).
- **Loop governance** (`loop_runtime`, `NoveltyGovernor`): standing lease
  renewal, quiet hours, drift report, and persistent first-seen
  host/recipient escalation.
- **Cognition organs, default-OFF** (`memory_gate_runtime`,
  `skill_quarantine_runtime`): memory writes land as redacted candidates
  (a DENY stores nothing; tainted/injected candidates keep only a hash and a
  redacted preview and can never be promoted — proven by a byte-level SQLite
  scan); skills install quarantined, hash-pinned, injection-scanned.
- **Remote safety**: non-loopback `/v1` binds refuse to start without issued
  tokens (`zeus pair --issue-v1-token`, TTL + revocation; the token's
  registration — not spoofable headers — decides identity) or an explicit
  unsafe flag.
- **Hardening from three external review rounds**: durable once-grant burns
  at EVERY gate (write-through grant store), TTL fail-closed approval
  resolution end to end (an expired park can never resolve approved),
  bounded hygiene stream buffering, `/v1` token lifecycle.
- **Conformance**: 88 frozen scenarios across gates 0–4, governance UX, loop
  governance, both host adapters, hygiene modes, remote safety, and receipt
  coherence. Suite: 1880 tests, ruff clean. `CONNECTING.md`.

### Changed

- The objective-run executor line (M1–M5) is demoted from product critical
  path to a conformance harness and `zeus dev` fallback, preserved on the
  `harness/executor-conformance` branch.
- `zeus` now opens the control-plane verbs; the previous CLI surface is
  reachable as `zeus dev …`.

### Pre-refoundation history

Everything below this entry (v0.1.0 through v6.1.0) is the pre-refoundation
exploration line: a standalone agent-platform attempt whose surviving organs
(trust loop spine, capability registry, graded approvals, objective risk/VoI,
authority kernel, evidence ledger) became the control plane's kernel. Old
tags remain valid history; their version numbers do not imply control-plane
maturity.

## v6.1.0 - 2026-06-10

### Added

- Trust Loop runtime package with a governed execution spine, 4-tier
  AUTO/NOTIFY/ASK/DENY authority decisions, action reversibility, approval
  envelopes, undo proof, hash-chained SQLite evidence ledger, decision
  receipts, approval queue, plan tournament, progressive trust proposal ledger,
  and skill manifest capability enforcement.
- Focused v6.1.0 red/green tests for unknown capability denial, irreversible
  approval gating, reversible in-scope execution through `CapabilityBroker`,
  tainted medium-risk escalation, ledger tamper detection, approval/undo proof,
  plan tournament selection, trust proposal review, skill manifest blocking,
  and release-gated checkpoint recognition.

### Changed

- Dogfood OpenAI chat execution now goes through the Trust Loop dispatcher before
  opening network execution. The direct chat-runtime HTTP call was removed.
- Version metadata is aligned to `zeus-agent==6.1.0` for Python packaging and
  `v6.1.0` for the GitHub release tag.
- Release-gated ULW now recognizes `v6.1.0` as the Trust Loop refoundation
  checkpoint and requires Trust Loop evidence before release.

### Notes

- `v6.1.0` is a refoundation release. It does not claim unrestricted production
  live execution. Broader MCP, gateway, browser, plugin, and remote sandbox
  surfaces still need the same Trust Loop retrofit before they should be opened.

## v6.0.0 - 2026-06-09

### Added

- Higher-Order Agent OS runtime that aggregates Zeus persona, Objective
  Compiler Workflow, governed live connectors, TUI cockpit contract, recursive
  improvement review, plugin skeleton, remote sandbox contract, tenant/auth
  contract, eval dashboard contract, persistent audit contract, and public
  production boundary.
- `higher-order-agent-os` CLI command and Python library facade method
  `ZeusAgent.higher_order_agent_os(...)`.
- Release-gated ULW `v6.0.0` checkpoint fields for the Agent OS product
  surface, TUI cockpit, recursive improvement review, plugin ecosystem
  skeleton, remote sandbox contract, and tenant/auth contract.

### Changed

- Version metadata is aligned to `zeus-agent==6.0.0` for Python packaging and
  `v6.0.0` for the GitHub release tag.
- Public README and Korean README now describe the Higher-Order Agent OS
  surface and operator cockpit command.

### Notes

- `v6.0.0` is the usable local-first Agent OS surface for trying Zeus as a
  governed, purpose-centered platform. Remote sandbox, multi-user hosted mode,
  unattended execution, unrestricted production live execution, and automatic
  memory promotion remain disabled by default.

## v5.8.0 - 2026-06-09

### Added

- Governed Live Connector Platform runtime that aggregates provider, MCP,
  gateway, and local sandbox connector preflight status through the same
  objective, lease, approval, promotion guard, broker evidence, credential
  scope, sandbox policy, and audit receipt requirements.
- Default governed live capability registry entries for MCP local smoke,
  gateway loopback smoke, and local sandbox smoke while preserving the provider
  local-smoke compatibility refs.
- `governed-live-connectors` CLI command and Python library facade method
  `ZeusAgent.governed_live_connectors(...)`.
- Release-gated ULW `v5.8.0` checkpoint fields for connector activation,
  broker-evidence requirements, and production-live boundary review.

### Changed

- Version metadata is aligned to `zeus-agent==5.8.0` for Python packaging and
  `v5.8.0` for the GitHub release tag.
- Public README and Korean README now include the Governed Live Connector
  Platform command and boundary.

### Notes

- `v5.8.0` allows trusted local smoke connector checks through broker evidence.
  It still keeps external provider, remote MCP, remote sandbox, browser live
  navigation, and production gateway delivery disabled by default.

## v5.5.0 - 2026-06-09

### Added

- Objective Compiler Workflow runtime that joins goal intelligence, ObjectiveRun,
  dynamic workflow planning, interview-gap UX, authority requirements, and
  evidence planning into one side-effect-free compile surface.
- `objective-compile-workflow` CLI command and Python library facade method
  `ZeusAgent.objective_compile_workflow(...)`.
- Release-gated ULW `v5.5.0` checkpoint fields for Objective Compiler UX,
  Dynamic Workflow Runtime, workflow DAG, evidence plan, deep-interview
  contract, and repair/replan UX.

### Changed

- Version metadata is aligned to `zeus-agent==5.5.0` for Python packaging and
  `v5.5.0` for the GitHub release tag.
- Public README and Korean README now include the Objective Compiler Workflow
  command and product boundary.

### Notes

- `v5.5.0` compiles clear objectives into workflow DAG and evidence plans, and
  asks focused interview questions for vague objectives. It still does not
  enable unrestricted production live execution by default.

## v5.0.0 - 2026-06-09

### Added

- Live Platform Beta runtime that aggregates productized status, Zeus persona,
  setup/status cockpit readiness, ObjectiveRun spine, governed live authority
  UX, CLI/Python surfaces, operator journey commands, and public beta boundary.
- `live-platform-beta` CLI command and Python library facade method
  `ZeusAgent.live_platform_beta(...)`.
- Release-gated ULW `v5.0.0` checkpoint fields for productized live platform
  beta, objective-to-live journey, authority UX beta, and public beta boundary.

### Changed

- Version metadata is aligned to `zeus-agent==5.0.0` for Python packaging and
  `v5.0.0` for the GitHub release tag.
- Public README, Korean README, command catalog, security boundary, and live
  architecture documentation now describe the v5.0.0 beta product surface.

### Notes

- `v5.0.0` is installable and usable as a governed local beta surface for
  objective runs, authority UX, persona/status, and public-boundary inspection.
  It still does not enable unrestricted production live execution by default.

## v4.5.0 - 2026-06-09

### Added

- Governed Live Slice runtime that wraps the existing governed live dispatcher
  with operator-facing missing-requirement UX.
- `governed-live-slice` CLI command and Python library facade method
  `ZeusAgent.governed_live_slice(...)`.
- Release-gated ULW `v4.5.0` checkpoint fields for governed live slice,
  authority UX, live preflight requirement map, and trusted loopback smoke
  availability.

### Changed

- Version metadata is aligned to `zeus-agent==4.5.0` for Python packaging and
  `v4.5.0` for the GitHub release tag.
- Public README, Korean README, command catalog, security boundary, and live
  architecture documentation now describe the Governed Live Slice boundary.

### Notes

- `v4.5.0` allows only the trusted local loopback smoke path through the
  existing broker evidence route. It still does not enable production external
  provider, MCP, gateway, browser, terminal, sandbox, or remote network
  execution by default.

## v4.1.0 - 2026-06-09

### Added

- ObjectiveRun runtime for turning a compiled objective into a persisted local
  run with goal contract, current plan, evidence records, and completion
  summary.
- `objective-start`, `objective-status`, and `objective-export` CLI commands for
  local objective run lifecycle inspection.
- Python library facade methods `ZeusAgent.objective_start(...)`,
  `ZeusAgent.objective_status(...)`, and `ZeusAgent.objective_export(...)`.
- Release-gated ULW `v4.1.0` checkpoint fields for objective execution spine
  availability, ObjectiveRun store availability, CLI availability, completion
  arbiter bridge, and evidence graph bridge.

### Changed

- Version metadata is aligned to `zeus-agent==4.1.0` for Python packaging and
  `v4.1.0` for the GitHub release tag.
- Public README, Korean README, command catalog, and security boundary now
  describe the ObjectiveRun spine and the v4.1.0 public boundary.

### Notes

- `v4.1.0` still keeps production live execution disabled by default.
  ObjectiveRun records local objective execution state and evidence obligations;
  it does not authorize provider, MCP, gateway, browser, terminal, sandbox, or
  remote network handlers by itself.

## v4.0.0 - 2026-06-06

### Added

- Productized Zeus Platform runtime that aggregates the Zeus persona,
  setup-plan surface, product cockpit, cognitive provider activation, plugin
  ecosystem, tenant/auth, and candidate-only learning contracts into one
  installable product checkpoint.
- `productized-platform` CLI command and Python library facade method for
  status, persona, setup, cockpit, operator-map, plugin/tenant/learning, and
  public-boundary scenarios.
- Release-gated ULW `v4.0.0` checkpoint fields for productized platform
  readiness, setup wizard availability, status cockpit availability, operator
  command map availability, and installable user journey availability.
- Public README and Hermes comparison documentation now describe the v4.0.0
  productized platform boundary.

### Changed

- Version metadata is aligned to `zeus-agent==4.0.0` for Python packaging and
  `v4.0.0` for the GitHub release tag.

### Notes

- `v4.0.0` keeps production live execution disabled by default. External
  provider execution, remote MCP server execution, external gateway delivery,
  browser live execution, remote sandbox execution, and unattended execution
  remain off until governed live adapters satisfy lease, approval, credential,
  audit, sandbox, cleanup, and release evidence gates.

## v3.1.0 - 2026-06-06

### Added

- Cognitive Provider Activation runtime that routes Goal Intelligence through
  the governed `model_runtime.ProviderRegistry` path.
- `cognitive-provider-activation` CLI command and Python library facade method
  `ZeusAgent.cognitive_provider_activation_runtime(...)`.
- Fake cognitive provider JSON output mode behind the `zeus.intent_schema`
  metadata contract, preserving the default fake provider response for existing
  callers.
- Release-gated ULW `v3.1.0` checkpoint fields for cognitive provider
  activation, model-runtime-to-goal-intelligence bridge, output schema gate,
  deterministic fallback, goal operating loop, and governed live thin-slice
  readiness.

### Changed

- Version metadata is aligned to `zeus-agent==3.1.0` for Python packaging and
  `v3.1.0` for the GitHub release tag.
- The public README banner image is replaced with the new Zeus portrait asset.

### Notes

- `v3.1.0` connects cognition to the provider runtime without opening
  unrestricted external provider execution, raw credential access, handler
  execution, or live production claims.

## v3.0.0 - 2026-06-06

### Added

- Stable Live Agent Platform contract that aggregates Goal Intelligence,
  Installable Live Platform, and Production Scale Platform readiness.
- `stable-release` now reports the `v3.0.0` stable Zeus platform objective
  instead of the earlier `v1.0.0` stable checkpoint.
- Release-gated ULW `v3.0.0` final checkpoint fields for stable goal
  intelligence, installable platform, production-scale platform, and public
  boundary readiness.

### Changed

- Version metadata is aligned to `zeus-agent==3.0.0` for Python packaging and
  `v3.0.0` for the GitHub release tag.
- Stable release reporting now treats the public platform as ready only when
  goal intelligence, installable live platform, and production-scale platform
  contracts all report ready.

### Notes

- `v3.0.0` is the stable governed live agent platform release. It still keeps
  unrestricted production live execution, browser live execution, remote
  sandbox execution, external gateway production delivery, MCP resources/prompts
  activation, and unattended execution disabled by default.

## v2.4.0 - 2026-06-06

### Added

- Production Scale Platform runtime for plugin ecosystem, remote sandbox policy,
  tenant/principal auth contract, and candidate-only learning operations.
- CLI command `production-scale-platform` and Python library facade method
  `ZeusAgent.production_scale_platform_runtime(...)`.
- Plugin ecosystem reporting that preserves manifest validation, permission
  policy, and quarantine without registering tools or executing handlers.
- Remote sandbox policy reporting for local, Docker, SSH, and remote backend
  interfaces with network egress, mount, and credential passthrough default
  denied.
- Tenant/auth contract reporting for tenant id, principal identity, scoped API
  keys, role/scope enforcement, cross-tenant default deny, and append-only
  audit requirements.
- Learning operations reporting for eval registry, error ledger,
  promotion-review, and candidate-only learning without automatic active rule or
  memory promotion.

### Changed

- Version metadata is aligned to `zeus-agent==2.4.0` for Python packaging and
  `v2.4.0` for the GitHub release tag.
- Release-gated ULW now recognizes `v2.4.0` as the Production Scale Platform
  checkpoint before the `v3.0.0` stable release.

### Notes

- `v2.4.0` is an operating-scale contract checkpoint. It still does not open
  unrestricted production live execution, remote sandbox execution, or
  unattended self-promotion.

## v2.3.0 - 2026-06-06

### Added

- Installable Live Platform runtime for package-level status reporting across
  provider, MCP, gateway, API, CLI, Python library, plugin manifest, local
  sandbox policy, and remote sandbox policy surfaces.
- CLI command `installable-live-platform` and Python library facade method
  `ZeusAgent.installable_live_platform_runtime(...)`.
- Plugin manifest install scenario that keeps valid plugin manifests
  quarantined until review and prevents tool registration or handler execution.
- Remote sandbox policy scenario that reports remote sandbox execution as
  blocked without opening network, Docker, SSH, or remote execution.
- Release-gated ULW `v2.3.0` checkpoint fields for installable live platform
  readiness and install surfaces.

### Changed

- Version metadata is aligned to `zeus-agent==2.3.0` for Python packaging and
  `v2.3.0` for the GitHub release tag.
- The public installable platform surface now exposes a single readiness
  contract instead of requiring users to inspect provider, MCP, gateway, plugin,
  sandbox, and API readiness separately.

### Notes

- `v2.3.0` remains an installable governed-live platform checkpoint. It does
  not claim unrestricted production external provider, MCP, gateway, browser,
  terminal, or remote sandbox execution.

## v2.2.0 - 2026-06-06

### Added

- Goal Intelligence Platform contract with structured `IntentFrame` output:
  desired outcome, acceptance criteria, constraints, entities, assumptions,
  unknowns, and confidence.
- Evidence-based `objective_understood` semantics. Zeus now treats an objective
  as understood only when acceptance criteria exist, high-impact unknowns are
  absent, and confidence meets the threshold.
- Slot-driven interview questions that target missing or low-confidence intent
  fields instead of returning a fixed generic question set.
- Deep interview loop inputs for interview answers, proceed override, residual
  assumptions, round count, and candidate-only context updates.
- Governed fake cognitive-provider seam that rejects malformed, prompt
  injection-like, authority-widening, or unsafe live-transport structured output.
- Work-loop bridge fields: `goal_contract_id`, `normalized_goal`, and
  `acceptance_criteria`.
- Release-gated ULW `v2.2.0` checkpoint fields for intent frames, acceptance
  criteria, deep interview loop, governed cognitive provider, and work-loop
  bridge readiness.

### Changed

- Version metadata is aligned to `zeus-agent==2.2.0` for Python packaging and
  `v2.2.0` for the GitHub release tag.
- Goal Intelligence Runtime is now the current public goal-intelligence
  contract version. The v2.0/v2.1 scaffolds remain represented in release-gate
  history, but the live runtime reports the v2.2 contract shape.

### Notes

- `v2.2.0` still does not open unsafe production external provider, MCP,
  gateway, browser, terminal, or remote sandbox execution by default. User
  context and ontology learning remain candidate-only with no auto-promotion.

## v2.1.0 - 2026-06-06

### Added

- Kernel-throughput integration runtime that routes governed live-capable
  provider smoke work through a trusted governance record, `CapabilityBroker`,
  scoped authority, approval, live promotion guard, and a broker evidence
  target before a handler can execute. Broker dispatch evidence is recorded
  before success is reported.
- Live capability registry for the governed `provider.local-smoke` capability.
- Red test pack for authority boundary properties, governed live dispatch, raw
  secret blocking, and `v2.1.0` release-gate broker-evidence requirements.
- Release-gated ULW `v2.1.0` checkpoint fields for broker dispatch and broker
  evidence enforcement.

### Changed

- Version metadata is aligned to `zeus-agent==2.1.0` for Python packaging and
  `v2.1.0` for the GitHub release tag.
- Release-gated ULW now reports the kernel-throughput integration checkpoint
  after the v2.0.0 goal-intelligence boundary.

### Notes

- `v2.1.0` does not open production external provider, MCP, gateway, browser,
  terminal, or remote sandbox execution. It narrows the next production-live
  step by making broker evidence a release-gate requirement before production
  readiness can be claimed.

## v2.0.0 - 2026-06-06

### Added

- Goal Intelligence Runtime and CLI command for objective understanding,
  deep-interview context candidates, adaptive replanning, workflow critic
  reporting, ontology-context smoke, and secret-boundary scenarios.
- Python library facade method for `goal_intelligence_runtime(...)`.
- Release-gated ULW `v2.0.0` checkpoint fields for objective understanding,
  deep interview, user context model, context ontology, adaptive replanning,
  workflow critic, and eval-loop readiness.

### Changed

- Version metadata is aligned to `zeus-agent==2.0.0` for Python packaging and
  `v2.0.0` for the GitHub release tag.
- Release-gated ULW now closes the compressed v1.8.0 -> v2.0.0 roadmap.

### Notes

- `v2.0.0` makes Zeus more purpose-aware by combining objective contracts,
  interview questions, user-context candidates, adaptive workflow selection,
  ontology context, and self-evolution status into one governed product
  surface. It still does not auto-promote memory, ontology, workflow patterns,
  active skills, or active rules.

## v1.9.0 - 2026-06-06

### Added

- Production Safe Live Platform Runtime and CLI command for live connector
  status, provider/MCP dry-run connection smoke, platform/execution boundary
  checks, activation-required blocking, and secret-boundary scenarios.
- A product-facing live connector map for external AI provider, MCP server,
  hosted API, gateway daemon, browser live navigation, terminal/sandbox, and
  remote sandbox surfaces.
- Release-gated ULW `v1.9.0` checkpoint fields for the live connector
  activation layer and production-safe live platform connection surfaces.
- Python library facade method for `production_live_platform_runtime(...)`.

### Changed

- Version metadata is aligned to `zeus-agent==1.9.0` for Python packaging and
  `v1.9.0` for the GitHub release tag.
- Release-gated ULW now advances `v1.8.0` to `v1.9.0`.

### Notes

- `v1.9.0` connects the live platform surfaces as governed status, dry-run, and
  fail-closed boundary contracts. It still does not start hosted API servers,
  gateway daemons, browser live navigation, remote sandboxes, or unrestricted
  external provider/MCP execution.

## v1.8.0 - 2026-06-06

### Added

- Zeus Identity Activation Runtime and CLI command for identity status, Korean
  call-name smoke, activation status, activation-check, and secret-boundary
  blocking scenarios.
- Explicit Zeus call-name contract for `Zeus` and `제우스`, including the
  Korean response `네, 제우스입니다.`.
- Release-gated ULW `v1.8.0` checkpoint fields for Zeus identity, call-name
  runtime, live activation contract, activation gate, objective, runtime lease,
  approval, credential binding, sandbox policy, and audit receipt requirements.
- Python library facade method for `identity_activation_runtime(...)`.

### Changed

- Version metadata is aligned to `zeus-agent==1.8.0` for Python packaging and
  `v1.8.0` for the GitHub release tag.
- Release-gated ULW now advances `v1.7.0` to `v1.8.0`.
- Persona cockpit and chat call-name handling now return `네, 제우스입니다.`
  for `제우스` / `제우스야`.
- RC macro wording now names the Zeus Live Platform Release Candidate instead
  of a Hermes-parity target.

### Notes

- `v1.8.0` does not open production live execution. It makes the common live
  activation prerequisites explicit before future provider, MCP, gateway,
  browser, terminal, sandbox, or hosted API execution can be claimed.

## v1.7.0 - 2026-06-06

### Added

- Real Product Platform Runtime and CLI command for product-facing persona,
  platform, live, model, MCP, and runtime cockpit aggregation.
- Product platform scenarios for status aggregation, Zeus work persona smoke,
  platform cockpit smoke, live status smoke, operator command map reporting,
  public boundary reporting, and secret-boundary blocking.
- Release-gated ULW `v1.7.0` checkpoint fields for product platform contract,
  persona surface, platform cockpit, live status surface, model/MCP/runtime
  status surfaces, operator command map, public boundary report, and product
  platform readiness.
- Python library facade method for `product_platform_runtime(...)`.

### Changed

- Version metadata is aligned to `zeus-agent==1.7.0` for Python packaging and
  `v1.7.0` for the GitHub release tag.
- Release-gated ULW now advances `v1.6.0` to `v1.7.0`.
- README, security policy, Hermes comparison, and live connection architecture
  now describe Real Product Platform Runtime as the seventh post-stable
  live-platform expansion.

### Notes

- `v1.7.0` makes Zeus feel more like a broad live platform shell by exposing a
  single product status surface and operator command map. It still does not
  start hosted API servers, gateway daemons, external provider transports,
  remote MCP production servers, browser live navigation, or remote sandboxes.

## v1.6.0 - 2026-06-06

### Added

- Real Self Evolution Runtime and CLI command for eval-learning smoke,
  reviewable skill proposal smoke, workflow critique memory recording,
  promotion blocking, and secret-boundary scenarios.
- Release-gated ULW `v1.6.0` checkpoint fields for skill eval, eval registry,
  skill evolution, skill learning, workflow learning, promotion review gates,
  and real self-evolution readiness.
- Python library facade method for `self_evolution_runtime(...)`.

### Changed

- Version metadata is aligned to `zeus-agent==1.6.0` for Python packaging and
  `v1.6.0` for the GitHub release tag.
- Release-gated ULW now advances `v1.5.0` to `v1.6.0`.
- README, security policy, Hermes comparison, and live connection architecture
  now describe Real Self Evolution Runtime as the sixth post-stable
  live-platform expansion.

### Notes

- `v1.6.0` can turn verified eval/workflow evidence into reviewable learning
  candidates and local critique memory. It does not auto-promote active skills,
  active rules, workflow patterns, authority, memory, or production live state.

## v1.5.0 - 2026-06-06

### Added

- Real Memory Operation Runtime and CLI command for local MemoryGraph smoke,
  Memory/Ontology wiki smoke, secret quarantine, retention deletion,
  skill-learning memory bridge, and promotion block scenarios.
- Release-gated ULW `v1.5.0` checkpoint fields for local memory operation,
  ontology/wiki operation, secret quarantine, retention deletion,
  skill-learning memory bridge, and real memory operation readiness.
- Python library facade method for `memory_operation(...)`.

### Changed

- Version metadata is aligned to `zeus-agent==1.5.0` for Python packaging and
  `v1.5.0` for the GitHub release tag.
- Release-gated ULW now advances `v1.4.0` to `v1.5.0`.
- README, security policy, Hermes comparison, and live connection architecture
  now describe Real Memory Operation Runtime as the fifth post-stable
  live-platform expansion.

### Notes

- `v1.5.0` writes only local reviewable memory facts, quarantine/delete records,
  and skill-learning bridge facts. It does not auto-promote memory, ontology,
  wiki pages, active rules, active skills, authority, or production live state.

## v1.4.0 - 2026-06-06

### Added

- Real Execution Runtime and CLI command for controlled local terminal/sandbox
  command smoke, live browser-navigation guard, network-command block, and
  remote sandbox/Docker-socket block checks.
- Release-gated ULW `v1.4.0` checkpoint fields for terminal smoke, sandbox
  command smoke, browser live guard, network/remote block readiness, and real
  execution runtime readiness.
- Python library facade method for `execution_runtime(...)`.

### Changed

- Version metadata is aligned to `zeus-agent==1.4.0` for Python packaging and
  `v1.4.0` for the GitHub release tag.
- Release-gated ULW now advances `v1.3.0` to `v1.4.0`.
- README, security policy, Hermes comparison, and live connection architecture
  now describe Real Execution Runtime as the fourth post-stable live-platform
  expansion.

### Notes

- `v1.4.0` executes only controlled local sandbox smoke paths and keeps live
  browser navigation, open network egress, remote sandbox execution, Docker/SSH
  backends, and production execution blocked.

## v1.3.0 - 2026-06-06

### Added

- Real Platform Runtime and CLI command for API dry-run reporting, gateway
  loopback session smoke, gateway external-delivery blocking, local session
  export redaction, and batch/ACP adapter smoke.
- Release-gated ULW `v1.3.0` checkpoint fields for gateway/API/session platform
  availability, API dry-run availability, gateway session smoke availability,
  session export availability, ACP/batch smoke availability, and real platform
  runtime readiness.
- Python library facade method for `platform_runtime(...)`.

### Changed

- Version metadata is aligned to `zeus-agent==1.3.0` for Python packaging and
  `v1.3.0` for the GitHub release tag.
- Release-gated ULW now advances `v1.2.0` to `v1.3.0`.
- README, security policy, Hermes comparison, and live connection architecture
  now describe Real Platform Runtime as the third post-stable live-platform
  expansion.

### Notes

- `v1.3.0` opens a governed API/gateway/session platform boundary. It still
  does not claim hosted API daemon readiness, external gateway delivery,
  webhook production execution, unattended operation, or credential material
  release.

## v1.2.0 - 2026-06-06

### Added

- Real MCP Runtime and CLI command for MCP catalog reporting, setup dry-run,
  server list, manifest inspection, governed fake-client test smoke, login
  dry-run, include/exclude policy, resource/prompt wrapper policy, and
  prompt-injection quarantine.
- Release-gated ULW `v1.2.0` checkpoint fields for real MCP runtime contract
  availability, MCP catalog runtime availability, setup dry-run availability,
  login dry-run availability, governed MCP smoke availability, and real MCP
  runtime readiness.
- Python library facade method for `mcp_runtime(...)`.

### Changed

- Version metadata is aligned to `zeus-agent==1.2.0` for Python packaging and
  `v1.2.0` for the GitHub release tag.
- Release-gated ULW now advances `v1.1.0` to `v1.2.0`.
- README, security policy, Hermes comparison, and live connection architecture
  now describe Real MCP Runtime as the second post-stable live-platform
  expansion.

### Notes

- `v1.2.0` opens a governed real MCP runtime boundary for catalog, setup,
  inspection, login dry-run, and fake-client MCP testing. It still does not
  claim unrestricted production remote MCP server execution, enabled MCP
  resources/prompts, unattended external MCP operation, or credential material
  release.

## v1.1.0 - 2026-06-06

### Added

- Real Provider Runtime and CLI command for provider profile reporting,
  governed local deterministic provider smoke, and controlled external provider
  receipt validation through explicit operator opt-in, endpoint allowlisting,
  scoped environment secret references, budget/timeout gates, audit, redaction,
  and no-production-claim reporting.
- Release-gated ULW `v1.1.0` checkpoint fields for real provider runtime
  contract availability, provider profile availability, governed external
  provider availability, local provider smoke availability, and real provider
  runtime readiness.
- Python library facade method for `provider_runtime(...)`.

### Changed

- Version metadata is aligned to `zeus-agent==1.1.0` for Python packaging and
  `v1.1.0` for the GitHub release tag.
- Release-gated ULW now advances `v1.0.0` to `v1.1.0` and prepares the
  sequential v1.2.0 through v1.7.0 expansion program.
- README, security policy, Hermes comparison, and live connection architecture
  now describe Real Provider Runtime as the first post-stable live-platform
  expansion.

### Notes

- `v1.1.0` opens a governed real provider runtime boundary. It still does not
  claim unrestricted production provider execution, unattended live operation,
  browser execution, remote sandbox execution, or automatic memory/skill
  promotion.

## v1.0.0 - 2026-06-06

### Added

- Stable Release runtime and CLI command for the governed live platform
  boundary.
- Python library facade method for `stable_release(...)`.
- Release-gated ULW `v1.0.0` checkpoint fields for stable governed live
  platform readiness and stable public release readiness.

### Changed

- Version metadata is aligned to `zeus-agent==1.0.0` for Python packaging and
  `v1.0.0` for the GitHub release tag.
- README, Hermes comparison, live connection architecture, master plan, and
  security policy now describe `v1.0.0` as the stable governed live platform
  release.
- Release-gated ULW now advances `v1.0.0-rc.9` to `v1.0.0`.

### Notes

- `v1.0.0` is stable for the public governed live platform boundary.
- It does not claim unrestricted external provider execution, production remote
  MCP execution, external gateway/webhook production delivery, browser live
  execution, remote sandbox execution, unattended live operation, or automatic
  memory/ontology/rule promotion.

## v1.0.0-rc.9 - 2026-06-06

### Added

- MCP Owned Client Live runtime and CLI command for governed remote MCP tool
  execution through explicit operator opt-in, endpoint allowlisting, scoped
  secret reference checks, credential handoff, remote transport policy, remote
  executor preflight, owned client receipt validation, audit, redaction,
  cleanup, resources/prompts disabled posture, and no-production-claim
  reporting.
- Release-gated `v1.0.0-rc.9` checkpoint fields for MCP owned client live
  contract availability, owned client transport availability, owned client
  adapter availability, and MCP owned client live readiness.
- Python library facade method for `mcp_owned_client_live(...)` so library
  callers can inspect the same owned-client MCP contract as the CLI.

### Changed

- Version metadata is aligned to `zeus-agent==1.0.0rc9` for Python packaging
  and `v1.0.0-rc.9` for the GitHub release tag.
- README, Hermes comparison, live connection architecture, and security policy
  now describe MCP Owned Client Live on top of Provider Owned Client Live.
- Release-gated ULW now advances `v1.0.0-rc.8` to `v1.0.0-rc.9`.

### Notes

- `v1.0.0-rc.9` is still governed and deterministic by default.
- MCP Owned Client Live validates the owned-client adapter path with policy,
  credential handoff, preflight, audit, redaction, cleanup, and
  resources/prompts disabled. It does not claim production remote MCP catalog
  readiness, unrestricted remote MCP execution, hosted SaaS readiness, or
  unattended live operation.

## v1.0.0-rc.8 - 2026-06-06

### Added

- Provider Owned Client Live runtime and CLI command for governed owned provider
  client execution through explicit operator opt-in, endpoint allowlisting,
  scoped secret reference checks, credential handoff, remote transport policy,
  remote executor preflight, owned client receipt validation, audit, redaction,
  cleanup, and no-production-claim reporting.
- Release-gated `v1.0.0-rc.8` checkpoint fields for provider owned client live
  contract availability, owned client transport availability, owned client
  adapter availability, and provider owned client live readiness.
- Python library facade method for `provider_owned_client_live(...)` so library
  callers can inspect the same owned-client live contract as the CLI.

### Changed

- Version metadata is aligned to `zeus-agent==1.0.0rc8` for Python packaging
  and `v1.0.0-rc.8` for the GitHub release tag.
- README, Hermes comparison, live connection architecture, and security policy
  now describe the Provider Owned Client Live checkpoint on top of Provider
  Live Opt-in.
- Release-gated ULW now advances `v1.0.0-rc.7` to `v1.0.0-rc.8`.

### Notes

- `v1.0.0-rc.8` is still governed and deterministic by default.
- Provider Owned Client Live validates the owned-client adapter path with
  policy, credential handoff, preflight, audit, redaction, and cleanup. It does
  not claim unrestricted production provider execution, hosted SaaS readiness,
  or unattended live operation.

## v1.0.0-rc.7 - 2026-06-06

### Added

- Provider Live Opt-in runtime and CLI command for explicit operator opt-in,
  endpoint allowlisting, scoped secret reference checks, remote transport
  policy, remote executor preflight, external provider receipt validation,
  audit, redaction, and no-production-claim reporting.
- Release-gated `v1.0.0-rc.7` checkpoint fields for provider live opt-in
  contract availability, external provider receipt availability, remote
  transport policy availability, remote executor preflight availability, and
  provider live opt-in readiness.
- Python library facade method for `provider_live_optin(...)` so library callers
  can inspect the same Provider Live Opt-in contract as the CLI.
- Secret-safe external receipt smoke coverage that proves missing opt-in,
  unallowlisted endpoints, and missing secrets fail closed before opening the
  external provider receipt path.

### Changed

- Version metadata is aligned to `zeus-agent==1.0.0rc7` for Python packaging
  and `v1.0.0-rc.7` for the GitHub release tag.
- README, Hermes comparison, live connection architecture, and security policy
  now describe the Provider Live Opt-in checkpoint on top of Memory Privacy
  Live.
- Release-gated ULW now advances `v1.0.0-rc.6` to `v1.0.0-rc.7`.

### Notes

- `v1.0.0-rc.7` is still governed and deterministic by default.
- Provider Live Opt-in `external-receipt-smoke` validates a controlled external
  receipt with operator opt-in, allowlist, preflight, audit, and redaction. It
  does not claim unrestricted production provider execution, hosted SaaS
  readiness, or unattended live operation.

## v1.0.0-rc.6 - 2026-06-06

### Added

- Memory Privacy Live runtime and CLI command for governed local MemoryGraph
  privacy checks, SQLite-backed schema readiness, secret quarantine, retention
  deletion, cross-session search default-deny posture, and no auto-promotion
  reporting.
- Release-gated `v1.0.0-rc.6` checkpoint fields for local memory store
  availability, SQLite backend availability, retention delete readiness, secret
  quarantine readiness, PII redaction readiness, cross-session search default
  deny, and local privacy readiness.
- Python library facade method for `memory_privacy_live(...)` so library callers
  can inspect the same local privacy contract as the CLI.
- Secret-safe contract output scrubber for memory privacy surfaces so redacted
  store values do not leave residual secret-like markers in public evidence.

### Changed

- Version metadata is aligned to `zeus-agent==1.0.0rc6` for Python packaging
  and `v1.0.0-rc.6` for the GitHub release tag.
- README, Hermes comparison, live connection architecture, and security policy
  now describe the Memory Privacy Live checkpoint on top of Sandbox Terminal
  Live.
- Release-gated ULW now advances `v1.0.0-rc.5` to `v1.0.0-rc.6`.

### Notes

- `v1.0.0-rc.6` is still local-first and deterministic by default.
- Memory Privacy Live can create local SQLite MemoryGraph state under the
  selected Zeus home for explicit smoke scenarios. It does not claim automatic
  memory writes from ordinary agent turns, cross-session search exposure,
  ontology promotion, learned-rule promotion, active rule writes, external
  network access, or production live readiness.

## v1.0.0-rc.5 - 2026-06-06

### Added

- Sandbox Terminal Live runtime and CLI command for governed local terminal
  planning, sandbox dispatch planning, browser live-navigation guard checks,
  lease-bound sandbox executor dispatch, approval-bound command execution, safe
  environment use, evidence capture, and cleanup.
- Release-gated `v1.0.0-rc.5` checkpoint fields for terminal facade
  availability, sandbox dispatch facade availability, tool sandbox executor
  availability, browser dispatch guard availability, local sandbox readiness,
  remote sandbox blocked posture, Docker blocked posture, SSH blocked posture,
  and browser live-navigation blocked posture.
- Python library facade method for `sandbox_terminal_live(...)` so library
  callers can inspect the same sandbox/terminal live-local contract as the CLI.
- Secret-safe network and remote blocks that prevent network, Docker socket,
  SSH, browser live navigation, and remote sandbox execution from reaching
  handlers.

### Changed

- Version metadata is aligned to `zeus-agent==1.0.0rc5` for Python packaging
  and `v1.0.0-rc.5` for the GitHub release tag.
- README, Hermes comparison, live connection architecture, and security policy
  now describe the Sandbox Terminal Live checkpoint on top of the Gateway Live
  Delivery boundary.

### Notes

- `v1.0.0-rc.5` is still local-first and deterministic by default.
- The Sandbox Terminal Live local smoke can execute an allowlisted local command
  in a temporary sandbox through a runtime lease, approval receipt, broker
  dispatch, safe environment, evidence capture, and cleanup. It does not claim
  browser live navigation, Docker/SSH/remote sandbox execution, hosted SaaS
  readiness, unattended execution, or hard-isolated remote runtime operation.

## v1.0.0-rc.4 - 2026-06-06

### Added

- Gateway Live Delivery runtime and CLI command for governed gateway status
  reporting, configured target allowlist, pairing proof, delivery envelope,
  delivery body, loopback transport, loopback HTTP delivery, audit, response
  redaction, and cleanup evidence.
- Release-gated `v1.0.0-rc.4` checkpoint fields for gateway settings,
  pairing, delivery envelope, delivery body, loopback transport, loopback HTTP,
  external delivery blocked posture, webhook blocked posture, and gateway live
  delivery readiness.
- Python library facade method for `gateway_live_delivery(...)` so library
  callers can inspect the same gateway live-delivery contract as the CLI.
- Secret-safe gateway live handling that blocks missing credential material and
  unallowlisted targets before loopback network access.

### Changed

- Version metadata is aligned to `zeus-agent==1.0.0rc4` for Python packaging
  and `v1.0.0-rc.4` for the GitHub release tag.
- README, Hermes comparison, live connection architecture, and security policy
  now describe the Gateway Live Delivery checkpoint on top of the MCP Live
  Server boundary.

### Notes

- `v1.0.0-rc.4` is still local-first and deterministic by default.
- The Gateway Live Delivery loopback smoke can open a session-local loopback
  HTTP server and execute the governed gateway delivery path when the operator
  supplies a scoped environment secret reference. It does not claim external
  gateway delivery, webhook production execution, hosted SaaS readiness,
  unattended execution, or hard-isolated remote runtime operation.

## v1.0.0-rc.3 - 2026-06-06

### Added

- MCP Live Server runtime and CLI command for governed MCP status reporting,
  loopback MCP HTTP smoke execution, and prompt-injection surface scanning.
- Release-gated `v1.0.0-rc.3` checkpoint fields for MCP catalog availability,
  activation policy, request envelope, loopback HTTP, credentialed HTTP,
  remote-server blocked posture, resources/prompts disabled posture, and
  MCP live-server readiness.
- Python library facade method for `mcp_live_server(...)` so library callers can
  inspect the same MCP live-server contract as the CLI.
- Secret-safe MCP live-server handling that blocks missing credential material
  before loopback network access and blocks unsafe prompt-injection markers
  without opening network access.

### Changed

- Version metadata is aligned to `zeus-agent==1.0.0rc3` for Python packaging
  and `v1.0.0-rc.3` for the GitHub release tag.
- README, Hermes comparison, live connection architecture, and security policy
  now describe the MCP Live Server checkpoint on top of the Provider Live API
  boundary.

### Notes

- `v1.0.0-rc.3` is still local-first and deterministic by default.
- The MCP Live Server loopback smoke can open a session-local loopback HTTP
  server and execute the governed MCP transport path when the operator supplies
  a scoped environment secret reference. It does not claim remote MCP server
  execution, resources/prompts activation, production live readiness, hosted
  SaaS readiness, unattended execution, or hard-isolated remote runtime
  operation.

## v1.0.0-rc.2 - 2026-06-06

### Added

- Provider Live API runtime and CLI command for governed provider live API
  status reporting and loopback provider smoke execution.
- Release-gated `v1.0.0-rc.2` checkpoint fields for provider live API
  readiness, loopback-only network opening, credential binding, secret material
  proof, execution authorization, audit, response redaction, and no external
  production-readiness claim.
- Python library facade method for `provider_live_api(...)` so library callers
  can inspect the same provider live API contract as the CLI.
- Secret-safe provider live handling that blocks missing or credential-like
  material without echoing raw secret-like values.

### Changed

- Version metadata is aligned to `zeus-agent==1.0.0rc2` for Python packaging
  and `v1.0.0-rc.2` for the GitHub release tag.
- README, Hermes comparison, live connection architecture, and security policy
  now describe the Provider Live API checkpoint on top of the earlier
  Production Foundation boundary.

### Notes

- `v1.0.0-rc.2` is still local-first and deterministic by default.
- The Provider Live API loopback smoke can open a session-local loopback server
  and execute the governed provider transport path when the operator supplies a
  scoped environment secret reference. It does not claim external non-loopback
  provider execution, production live readiness, hosted SaaS readiness,
  unattended execution, or hard-isolated remote runtime operation.

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
