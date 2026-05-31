# Zeus Implementation Status

## Implemented

1. Repo bootstrap: package metadata, CLI entrypoint, security policy, license.
2. Local data foundation: private `ZEUS_HOME` layout, event log, run store.
3. Core schemas: GoalContract, ExecutionSpec, TraceEvent, ApprovalRecord.
4. Blueprint mode: deterministic goal-to-spec generation with risk inference.
5. Approval loop: approve, reject, status, and recent-runs CLI commands.
6. Sandbox runtime: approval-gated local process execution, checkpoints,
   scrubbed environment, budget timeout, network/destructive command policy.
7. Sisyphus runner: approved-goal pursuit, progress report, explicit escalation
   for blocked implementation, evidence-backed status.
8. Mneme truth layer: evidence JSONL, checkpoint evidence, command evidence,
   diff gate from git status or checkpoint comparison.
9. Skill lifecycle: draft, test, promote, retire, local SKILL.md storage.
10. Provider/tool/GitHub prep: secret-free provider auth refs, model routes,
    tool registry, GitHub publish preparation plan.
11. Hermes P0 absorption: guarded `ZeusAgentSession`, self-registering tool
    broker, SQLite state/search index, content-addressed checkpoint/restore,
    large-output artifact persistence, command risk classifier, background
    skill review.
12. Hermes P1 absorption: runtime backend slots, plugin/MCP/tool-pack registry,
    cron-style schedule registry, and context compaction helpers.
13. Hermes P2 absorption: gateway adapter registry, trajectory export, and
    local observability/doctor report.

## Current Boundary

- The default sandbox is process-level policy enforcement, not Firecracker or
  container hard isolation yet. Docker/SSH/Modal/Daytona/Singularity/microVM
  are represented as policy-gated backend slots, not active executors.
- Sisyphus now has a guarded agent session and tool broker, but it does not yet
  attach a live model transport that synthesizes arbitrary code changes.
- Gateway, MCP, plugin, and cron registries record intent/configuration only;
  they do not perform outbound sends, daemon installs, or remote execution.
- Provider auth stores only environment variable names, never API key values.
- GitHub publishing is prep-only until the user explicitly asks for upload.

## Verification

- `uv run --extra dev pytest`: 17 passed.
- `uv run python -m compileall -q src tests`: passed.
- CLI smoke with isolated `ZEUS_HOME`: init, blueprint, approve,
  sandbox-snapshot, sandbox-run, execute, skill-draft, provider-add,
  github-prep passed.
- Hermes absorption smoke with isolated `ZEUS_HOME`: agent-run,
  runtime-backends, plugin-register, cron-add, gateway-register,
  trajectory-export, doctor passed.
