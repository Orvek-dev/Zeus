# Zeus System Design

Status: Draft v0.1
Target repository: `Orvek-dev/Zeus`
Default posture: local-first, local-only, sandboxed, evidence-backed

## 1. Product Thesis

Zeus is not only a sandbox executor. Zeus is an agent.

It should be comfortable for lightweight conversation, strong enough to turn a
user goal into a concrete workflow blueprint, and disciplined enough to execute
only inside approved boundaries.

Core sentence:

> Zeus is a goal-driven agent that escalates from conversation to blueprint to
> sandboxed execution only when user intent, risk, and approval align.

Hermes remembers and governs. Zeus persists, proves, executes, and improves.

## 2. What Zeus Inherits From Hermes

Hermes already has several mature architectural primitives. Zeus should not
copy Hermes as a monolith, but should inherit its proven patterns.

| Hermes primitive | Zeus inheritance |
|---|---|
| Agent runtime, provider setup, model routing, CLI/TUI, skills, tool registry | Agent Experience and Runtime layers |
| Capability policy, preflight, approval, budget gate | Aegis Policy Gate |
| Context Gate and task profile routing | Engagement Router and Context Router |
| Goal Contract and Goal State | Hera Contract and Sisyphus Core |
| Coding Harness and Local PR Runner | Apollo Verifier and Diff Gate |
| tmux Orchestra | Olympus Control Room |
| Mneme v2 operational memory | Mneme Truth Layer |
| Obsidian ontology governance | Hestia Vault and Zeus Ontology |
| App Lab proposal -> approval -> handoff -> review | Blueprint -> approval -> sandbox execution -> review |

Hermes' strongest lesson:

> Capture operational evidence broadly, but promote durable knowledge narrowly.

## 2.1 Hermes Absorption Pass

Zeus now absorbs Hermes in layers instead of copying it as a monolith.

P0 runtime substrate:

- Agent session loop around governed tool calls.
- Self-registering tool broker.
- SQLite state/search index.
- Restorable content-addressed checkpoints.
- Command risk classifier.
- Large tool-output artifact storage.
- Background memory/skill review.

P1 extensibility substrate:

- Runtime backend slots for local, Docker, SSH, Modal, Daytona, Singularity,
  and future microVM execution.
- Plugin, MCP, and tool-pack registry.
- Cron-style schedule registry.
- Context compaction helpers.

P2 platform substrate:

- Gateway adapter registry.
- Trajectory export for evaluation and replay.
- Local observability report.

Absorption rule:

> Hermes supplies platform breadth; Zeus keeps GoalContract, approval, sandbox,
> Mneme evidence, and Sisyphus as the governing center.

## 3. Operating Modes

Zeus must not trigger the full execution engine for every user turn. The first
layer is an Engagement Router.

| Mode | Purpose | Execution engine |
|---|---|---|
| Chat Mode | Lightweight conversation, questions, brainstorming, naming, explanations | Off |
| Advice Mode | Design, critique, architecture discussion, non-mutating guidance | Off |
| Blueprint Mode | Produce GoalContract, assumptions, architecture, tools, risk, verification | Off |
| Execute Mode | Run approved plan in sandbox | On |
| Review Mode | Show diff, artifacts, evidence, risks, and final choices | Read-only |

Explicit triggers:

- `/zeus`
- `/goal`
- `/blueprint`
- `/execute`
- "실제로 만들어줘"
- "자동화해줘"
- "샌드박스에서 구현해줘"
- "워크플로우를 만들어 실행해줘"

Implicit triggers:

- User requests a runnable artifact, script, app, automation, workflow, agent,
  integration, or repeatable system.
- The request contains completion-oriented language such as "끝까지",
  "실행 가능하게", "프로토타입", "자동화", "구현".

Non-triggers:

- Casual conversation.
- Emotional support.
- Naming and branding discussion.
- Simple explanation.
- Brainstorming without artifact request.
- "어떻게 생각해?" style exploration.

## 4. Two-Step Human Loop

Zeus uses a two-stage human loop.

Stage 1: Blueprint Approval

Zeus may analyze, inspect, research, and draft a plan, but it does not execute
mutating work. It returns:

- GoalContract.
- Assumptions.
- Acceptance criteria.
- Tool/API/MCP candidates.
- Sandbox plan.
- Risk class.
- Budget.
- Expected artifacts.
- Verification plan.

The user can approve, edit, reject, or ask for another blueprint.

Stage 2: Execution Approval

After approval, Zeus compiles the blueprint into an ExecutionSpec and starts the
sandboxed run. Execution still pauses for high-risk actions:

- Credential use.
- Paid API calls.
- External API writes.
- Public/customer messages.
- Production mutation.
- Git push or deploy.
- Secret access or storage.
- Destructive operations outside sandbox scope.

## 5. Mythology Module Map

Use mythology names as codenames, but public docs should pair them with
functional names.

| Codename | Functional name | Responsibility |
|---|---|---|
| Zeus Core | Control Plane | Top-level orchestration and run lifecycle |
| Sisyphus Core | Goal Persistence Engine | Keeps pushing toward the approved goal |
| Hera Contract | Goal Contract | User intent, constraints, assumptions, acceptance criteria |
| Athena Planner | Blueprint Planner | Intent analysis, architecture, task graph |
| Hephaestus Builder | Sandboxed Builder | Code/file generation and artifact creation |
| Apollo Verifier | Verification Engine | Tests, build, acceptance checks, judge support |
| Aegis | Policy and Approval Gate | Capability, budget, approval, security decisions |
| Artemis Guard | Sandbox Boundary Guard | Filesystem, network, scope, resource isolation |
| Poseidon Gateway | External Tool/API/MCP Gateway | Controlled egress and external service routing |
| Hestia Vault | Local Data Store | Local-first private state and ontology store |
| Mneme | Truth and Evidence Layer | Run memory, proof ledger, handoff packages |
| Ariadne Thread | Trace/Event Stream | Replayable event sourcing and provenance |
| Demeter Growth | Skill Evolution | Skill candidates, evals, promotion, deprecation |
| Hermes Bridge | Connector Layer | Provider, tool, messaging, and integration heritage |
| Ares Redteam | Adversarial Review | Security review, chaos, misuse and failure probes |
| Dionysus Lab | Creative Exploration | Experimental ideation and generative workflows |
| Aphrodite Studio | Presentation Layer | UX, design, marketing, visual polish |
| Hades Archive | Cold Archive/Quarantine | Deprecated, blocked, dead, or quarantined artifacts |

Artifacts:

| Artifact codename | Function |
|---|---|
| Thunderbolt | Approved execution dispatch |
| Caduceus | Tool broker and MCP mediation |
| Trident | Network policy and egress control |
| Hammer and Anvil | Build/edit/apply-patch pipeline |
| Helm of Hades | Secret redaction and hidden credential boundary |
| Ariadne Thread | Trace replay and provenance chain |
| Golden Fleece | Final verified artifact bundle |
| Medusa Head | Quarantined hostile evidence |
| Achilles Shield | Evidence cockpit and run status surface |

## 6. Top-Level Architecture

```text
User
  |
  v
Agent Experience Layer
  - CLI / TUI
  - local web dashboard
  - slash commands
  - approvals inbox
  - artifact viewer
  - run history / resume
  |
  v
Engagement Router
  - chat
  - advice
  - blueprint
  - execute
  - review
  |
  v
Goal-to-Agent Control Plane
  - Hera Contract
  - Athena Planner
  - Sisyphus Core
  - Aegis Policy Gate
  - ExecutionSpec Compiler
  |
  v
Execution Plane
  - Hephaestus Builder
  - Artemis Sandbox Guard
  - Poseidon Gateway
  - Tool Broker / MCP Layer
  - Apollo Verifier
  |
  v
Truth and Data Plane
  - Mneme Evidence Ledger
  - Ariadne Event Stream
  - Hestia Local Vault
  - Demeter Skill Evolution
  - Hades Archive
```

Current code map:

```text
agent/session.py           ZeusAgentSession and tool-call loop
tools/registry.py          self-registering governed tool broker
runtime/checkpoints.py     content-addressed checkpoint and restore
runtime/backends.py        execution backend slots
storage/state.py           SQLite sessions/messages/evidence/artifacts
core/plugins.py            plugin/MCP/tool-pack registry
core/scheduler.py          cron-style schedule registry
gateway/adapters.py        gateway adapter registry
eval/trajectory.py         trajectory export
observability/reports.py   local doctor report
```

## 7. Sisyphus Core

Sisyphus is the persistence engine.

It prevents the agent from giving explanations when the user asked for a
working system. It also prevents endless loops.

Loop:

```text
GoalContract
  -> TaskGraph
  -> NextConcreteStep
  -> Action / Tool / Sandbox
  -> Observation
  -> ProgressCheck
  -> Replan or Continue
  -> Done / Blocked / NeedsApproval
```

Rules:

- If a next safe step exists, continue.
- If the task is risky, request approval.
- If progress stalls, replan.
- If oscillation is detected, stop and show why.
- If budget is exhausted, pause with evidence.
- If acceptance criteria are not met, do not declare done.
- If evidence is missing, do not claim the action happened.

Progress signals:

- Task graph node completed.
- New artifact created.
- Diff changed.
- Test/build result improved.
- Failing count decreased.
- Verification coverage increased.
- User-approved assumption resolved.

Stuck signals:

- Same error repeated.
- Same diff reverted/reapplied.
- No new event after N attempts.
- Repair attempts exceed budget.
- Required approval or input missing.

## 8. Mneme Truth Layer

Mneme is the truth layer, not because it knows absolute truth, but because it
forces claims to be backed by observed evidence.

Rule:

> No evidence, no claim. No verification, no done.

Every user-visible claim should map to evidence:

| Claim | Required evidence |
|---|---|
| "I changed code" | diff, changed files, timestamp |
| "I ran tests" | command, exit code, stdout/stderr |
| "The app works" | server start, health check, screenshot or HTTP response |
| "I used an API" | preflight, tool call, redacted request metadata |
| "I am blocked" | failed step, error output, next required input |

User-facing commands:

```text
/zeus status
/zeus trace
/zeus evidence
/zeus diff
/zeus approvals
/zeus artifacts
/zeus why-stuck
/zeus resume
```

## 9. Skill Evolution

Zeus should use Skill.md files as performance amplifiers, not as decorative
prompt snippets.

Inspired by SkillOpt-style skill optimization:

```text
Run succeeds or fails
  -> Extract reusable pattern
  -> Create Skill Candidate
  -> Evaluate on similar tasks
  -> Promote to active Skill.md
  -> Track usage and regression
  -> Improve or deprecate
```

Skill states:

```text
draft
candidate
validated
active
deprecated
blocked
```

Skill types:

- Human-authored skill: user writes or approves procedure.
- Agent-discovered skill: Zeus proposes after repeated success/failure.
- Project skill: local project-specific workflow.
- Domain skill: reusable across projects.
- Safety skill: risk, verification, or red-team procedure.

Promotion rules:

- Agent-discovered skills are never auto-active by default.
- A skill must include trigger conditions, procedure, validation method, and
  rollback/deprecation conditions.
- A skill must not contain secrets or raw untrusted external instructions.
- Skill evaluation must produce traceable results.

## 10. Local Ontology

Zeus needs a flexible ontology, not a rigid fixed taxonomy.

Principles:

- Event stream is source of operational truth.
- Ontology is derived from events and curated artifacts.
- Raw external content is evidence, not authority.
- Long-term knowledge requires promotion.
- Everything is local-only by default.

Entity classes:

```text
UserGoal
GoalContract
Assumption
AcceptanceCriterion
ExecutionSpec
Run
TaskNode
Sandbox
Tool
ToolCall
PolicyDecision
Approval
Observation
CodeChange
Diff
Artifact
Verification
Failure
RepairAttempt
Skill
SkillCandidate
MemoryCandidate
ExternalSource
SecurityFinding
```

Relationship types:

```text
fulfills
derives_from
requires
gates
produces
modifies
checks
blocks
caused_by
addresses
supports
contradicts
promotes_to
supersedes
quarantines
```

Ontology rule:

> Zeus may remember operations automatically, but may learn only through
> verified promotion.

## 11. Local-First Data Layout

Default path:

```text
~/.zeus/
  config/
    config.yaml
    capability-policy.yaml
    model-router.yaml
    tool-registry.yaml
    network-policy.yaml
  secrets/
    README.md
  data/
    events/
      trace.jsonl
    runs/
      <run_id>/
        goal-contract.json
        blueprint.md
        execution-spec.json
        approvals.jsonl
        tool-calls.jsonl
        observations.jsonl
        diffs/
        artifacts/
        verification-report.json
        final-report.md
    ontology/
      entities.jsonl
      relationships.jsonl
      snapshots/
    memory/
      working/
      episodic/
      semantic/
      promotion-queue/
    skills/
      candidates/
      active/
      evals/
    security/
      audit.jsonl
      policy-decisions.jsonl
      secret-scan-results.jsonl
    archive/
      quarantine/
      cold/
  sandboxes/
    <sandbox_id>/
  cache/
  logs/
```

File permissions:

- Directories containing private state: `0700`.
- JSONL logs, state, approvals, secrets metadata: `0600`.
- Exported public bundles must be explicitly generated and secret-scanned.

## 12. Core Schemas

GoalContract:

```json
{
  "schema_version": "zeus-goal-contract-v1",
  "goal_id": "goal_...",
  "raw_user_request": "...",
  "normalized_goal": "...",
  "mode": "blueprint | execute",
  "deliverables": [],
  "acceptance_criteria": [],
  "assumptions": [],
  "constraints": {
    "network": "deny_by_default",
    "budget_seconds": 900,
    "max_repair_attempts": 5
  },
  "risk_level": "low | medium | high",
  "requires_human_approval": [],
  "forbidden_actions": [],
  "allowed_paths": [],
  "approval_state": "not_requested | approved | rejected"
}
```

ExecutionSpec:

```json
{
  "schema_version": "zeus-execution-spec-v1",
  "run_id": "run_...",
  "goal_contract_id": "goal_...",
  "environment": {
    "provider": "local | docker | firecracker | vercel_sandbox",
    "base_image": "python:3.12-slim",
    "network": "deny_by_default",
    "cpu_limit": 2,
    "memory_mb": 4096,
    "timeout_seconds": 900
  },
  "workspace": {
    "root": "/workspace",
    "input_dir": "/workspace/input",
    "output_dir": "/workspace/output"
  },
  "steps": [],
  "tools_required": [],
  "verification_rules": [],
  "budgets": {}
}
```

TraceEvent:

```json
{
  "schema_version": "zeus-trace-event-v1",
  "event_id": "evt_...",
  "run_id": "run_...",
  "parent_id": "",
  "timestamp": "ISO-8601",
  "event_type": "tool_call | observation | approval | verification | failure",
  "actor": "zeus | user | sandbox | verifier",
  "payload": {},
  "redaction_status": "clean | redacted | quarantined"
}
```

SkillCandidate:

```json
{
  "schema_version": "zeus-skill-candidate-v1",
  "skill_id": "skill_...",
  "name": "string",
  "source_runs": [],
  "trigger_conditions": [],
  "procedure_summary": "",
  "validation_method": "",
  "risk_level": "low | medium | high",
  "status": "candidate",
  "promotion_requirements": []
}
```

## 13. Security Model

Zeus is open source, so defaults must be hostile-environment safe.

Threats:

- Prompt injection from web, docs, emails, MCP outputs, logs, READMEs.
- Tool poisoning from malicious tool/MCP descriptions.
- Excessive agency from broad tool access.
- Secret leakage into logs, memory, prompts, screenshots, artifacts.
- Supply-chain risk from package installs and generated code.
- Local web UI exposure.
- Runaway loops consuming cost or modifying too much.

Defenses:

- Local-only telemetry by default.
- No remote analytics by default.
- Network deny by default in sandboxes.
- Explicit egress policy through Poseidon Gateway.
- Tool calls go through Caduceus Tool Broker.
- High-risk actions go through Aegis approval.
- Secret scanner before memory, artifact export, and skill promotion.
- External content stored as `untrusted_evidence`.
- Tool/MCP registry hash and source provenance.
- Community skills/plugins enter quarantine first.
- Sandbox artifacts scanned before export.
- Local UI binds to `127.0.0.1` by default.
- Local UI requires auth token if enabled.
- Event log redacts secrets before persistence.
- Raw credential values are never stored in Zeus state.

Credential model:

```text
AI provider keys      -> local secret files or OS keychain
MCP/API credentials   -> provider-scoped secret files
Sandbox credentials   -> short-lived injection through broker only
Logs and ontology     -> no raw secrets, ever
```

## 14. AI Provider Auth and Model Routing

Zeus should preserve Hermes-like user convenience.

Required features:

- `zeus setup`
- `zeus doctor`
- `zeus models`
- `zeus auth`
- `zeus tools`
- `zeus skills`
- `zeus status`

Provider support:

- OpenAI.
- Anthropic.
- OpenRouter.
- Local OpenAI-compatible endpoints.
- Future provider adapters through plugin interface.

Model routing:

| Route | Use |
|---|---|
| quick | Lightweight chat and simple planning |
| deep | Blueprint, design, research, risk analysis |
| builder | code/file generation in sandbox |
| verifier | strict JSON/checklist/judge tasks |
| redteam | adversarial review |
| cheap | low-cost summarization and classification |

The model router should be explicit and auditable. Provider fallback must be
recorded in the trace.

## 15. Tool Broker and MCP Layer

The model should not call raw tools directly.

Flow:

```text
LLM proposed tool call
  -> schema validation
  -> permission check
  -> argument sanitization
  -> risk classification
  -> approval gate if needed
  -> rate/budget limit
  -> secret redaction
  -> audit event
  -> actual tool call
```

Tool risk classes:

| Risk | Examples |
|---|---|
| Low | read sandbox file, run tests, build project |
| Medium | install package, start local server, read internet |
| High | credential use, external API write, public message, deploy |
| Blocked | secret exfiltration, destructive host mutation, production write without approval |

## 16. Sandbox Runtime

Sandbox is not only isolation. It is the ground-truth oracle.

It converts model hypotheses into observed reality:

- exit code.
- stdout/stderr.
- file existence.
- test results.
- build results.
- HTTP responses.
- screenshots.
- artifact hashes.

Sandbox providers:

- Local directory sandbox for MVP.
- Docker for common code execution.
- gVisor/Firecracker-style provider later for stronger isolation.
- Vercel Sandbox or remote provider as optional plugin, never default.

Required features:

- Filesystem isolation.
- Snapshot/restore.
- CPU/memory/time quotas.
- Network policy.
- Artifact export.
- Preview server.
- Test runner.
- Secret-free logs.

## 17. Verification and Repair

Verification hierarchy:

```text
syntactic
  -> parse, compile, typecheck
behavioral
  -> tests, smoke checks, API health
acceptance
  -> success criteria from GoalContract
critic
  -> model or human review when deterministic checks are insufficient
```

Self-generated tests are not enough. Mitigations:

- Derive acceptance tests from approved GoalContract.
- Keep verifier role separate from builder role.
- Prefer deterministic checks over model judgement.
- Require human review for high-risk or ambiguous acceptance.

Repair loop:

```text
execute
  -> observe
  -> verify
  -> diagnose
  -> patch
  -> rerun targeted checks
  -> success or pause with evidence
```

## 18. Agent UX

Minimum CLI:

```text
zeus
zeus setup
zeus doctor
zeus models
zeus auth
zeus tools
zeus skills
zeus goal "..."
zeus blueprint "..."
zeus execute <blueprint_id>
zeus approve <approval_id>
zeus runs
zeus status <run_id>
zeus evidence <run_id>
zeus diff <run_id>
zeus artifacts <run_id>
zeus resume <run_id>
zeus archive <run_id>
```

Slash commands:

```text
/goal
/blueprint
/execute
/approve
/reject
/status
/trace
/evidence
/diff
/artifacts
/why-stuck
/skills
/models
```

Dashboard:

- Active run list.
- Approval inbox.
- Evidence cockpit.
- Diff viewer.
- Artifact viewer.
- Sandbox logs.
- Skill candidates.
- Security findings.

## 19. MVP Roadmap

Phase 0: Documentation and skeleton

- README.
- System design.
- Local data layout.
- JSON schemas.
- Security policy.

Phase 1: Local agent shell

- CLI.
- Provider auth.
- Model router.
- Chat/Blueprint modes.
- Local event log.

Phase 2: Goal and blueprint

- Engagement Router.
- GoalContract.
- Blueprint generator.
- Human approval storage.

Phase 3: Sandbox MVP

- Local/Docker sandbox.
- File write/read.
- Shell execution.
- Artifact export.
- ExecutionSpec.

Phase 4: Verification and Sisyphus

- Test/build runners.
- Repair loop.
- Stuck detection.
- Evidence cockpit.

Phase 5: Skill evolution

- Skill registry.
- Skill candidate extraction.
- Eval dataset.
- Promotion gate.

Phase 6: Ontology and Mneme-grade truth layer

- Entities/relationships.
- Run summaries.
- Claim-to-evidence mapping.
- Memory promotion queue.

Phase 7: Open-source hardening

- Threat model.
- Plugin quarantine.
- MCP/tool integrity.
- Secret scanning.
- Local UI auth.
- Reproducible security tests.

## 20. Non-Goals

Initial Zeus should not:

- Auto-deploy to production.
- Push to GitHub by default.
- Store data in hosted services by default.
- Use external telemetry by default.
- Execute high-risk actions without approval.
- Treat agent-generated skills as active without validation.
- Treat external content as instruction authority.

## 21. Reference Projects

- Hermes Agent: runtime, skills, providers, gateway, memory, tool registry.
- Hermes local operating layer: policy, preflight, goal state, evidence, App Lab.
- Microsoft SkillOpt: skill optimization and validation mindset.
- Sandcastle: sandboxed coding agent workflow.
- tmux: long-running observable session model.
- Mneme: scoped operational memory, handoff, and gates.
- oh-my-openagent: goal-driven persistence inspiration.

## 22. Final Architecture Statement

Zeus is an agent with four promises:

1. It does not execute by default.
2. It does not claim completion without evidence.
3. It does not cross risk boundaries without approval.
4. It improves by turning verified workflows into validated skills.

Short form:

> Zeus persists, proves, and improves.
