# Zeus Command Catalog

[English README](../README.md) · [한국어 README](../README.ko.md)

This catalog collects practical local commands for the public Zeus surfaces.
The README intentionally keeps only the first-run commands.

## First Run

```sh
zeus kernel-status
zeus productized-platform --scenario status --json
zeus cognitive-provider-activation --scenario fake-provider-intent --objective "Zeus, turn my goal into a governed workflow." --json
zeus goal-intelligence-runtime --scenario understand-objective --objective "Build a research backed coding workflow with parallel workers." --task-count 6 --requires-code --requires-research --json
zeus objective-start --objective "Zeus, turn my goal into an evidence-backed run." --acceptance-criterion objective-run-created --json
zeus release-gated-ulw --target-version v4.1.0 --json
```

## Product And Goal Intelligence

```sh
zeus productized-platform --scenario status --json
zeus productized-platform --scenario zeus-persona --json
zeus productized-platform --scenario setup-status --json
zeus productized-platform --scenario cockpit --json
zeus productized-platform --scenario public-boundary --json
zeus goal-intelligence-runtime --scenario understand-objective --objective "Build a governed workflow." --json
zeus goal-intelligence-runtime --scenario deep-interview --objective "Build a local governed workflow." --interview-answer "Complete means CLI JSON includes acceptance criteria and no unsafe live execution." --json
zeus goal-intelligence-runtime --scenario adaptive-replan --objective "Implement provider, MCP, gateway, and sandbox live platform slices with independent review." --task-count 8 --requires-code --requires-research --json
zeus cognitive-provider-activation --scenario fake-provider-intent --json
zeus cognitive-provider-activation --scenario external-provider-block --json
zeus cognitive-provider-activation --scenario unsafe-output-block --json
```

## Objective Runs

```sh
zeus objective-start --objective "Zeus, turn this objective into an evidence-backed run." --session-id local-demo --principal-id operator.local --acceptance-criterion objective-run-created --json
zeus objective-status --run-id <run-id-from-objective-start> --json
zeus objective-export --run-id <run-id-from-objective-start> --json
```

Objective runs persist locally under the selected Zeus home. Completion remains
blocked until each acceptance criterion has matching evidence.

## Release And Platform Status

```sh
zeus release-gated-ulw --target-version v4.1.0 --json
zeus stable-release --json
zeus production-live-platform-runtime --scenario status --json
zeus production-live-platform-runtime --scenario provider-mcp-smoke --json
zeus production-live-platform-runtime --scenario platform-execution-boundary --json
zeus platform-runtime --scenario status --json
zeus platform-runtime --scenario api-dry-run --json
zeus platform-runtime --scenario gateway-loopback-smoke --json
zeus platform-runtime --scenario session-secret-boundary --json
zeus platform-runtime --scenario batch-acp-smoke --json
```

## Provider And MCP Boundaries

```sh
zeus provider-runtime --scenario status --json
zeus provider-runtime --scenario local-deterministic-smoke --message "hello Zeus" --json
ZEUS_V110_PROVIDER_KEY=provider-v110-material-value zeus provider-runtime --scenario external-receipt-smoke --json
zeus mcp-runtime --scenario status --json
zeus mcp-runtime --scenario setup-dry-run --server-id mcp.github --json
zeus mcp-runtime --scenario inspect --server-id mcp.github --include-tools repo.search,issues.list --exclude-tools issues.list --json
zeus mcp-runtime --scenario test-loopback --server-id mcp.github --include-tools repo.search --json
zeus mcp-runtime --scenario login-dry-run --server-id mcp.github --json
zeus mcp-runtime --scenario blocked-resource-prompt --resources --prompts --json
```

## Execution, Memory, And Self-Evolution

```sh
zeus execution-runtime --scenario status --json
zeus execution-runtime --scenario local-execution-smoke --json
zeus execution-runtime --scenario browser-blocked-live --json
zeus execution-runtime --scenario blocked-network --json
zeus execution-runtime --scenario blocked-remote --json
zeus memory-operation --scenario status --json
zeus memory-operation --scenario local-store-smoke --json
zeus memory-operation --scenario ontology-wiki-smoke --json
zeus memory-operation --scenario secret-quarantine --json
zeus memory-operation --scenario retention-delete --json
zeus memory-operation --scenario skill-learning-bridge --json
zeus memory-operation --scenario promotion-block --json
zeus self-evolution-runtime --scenario status --json
zeus self-evolution-runtime --scenario eval-learning-smoke --json
zeus self-evolution-runtime --scenario skill-proposal-smoke --json
zeus self-evolution-runtime --scenario workflow-critique-memory --json
zeus self-evolution-runtime --scenario promotion-block --json
```

## Live-Capable Smoke Boundaries

These commands remain governed smoke or blocked-boundary checks. They do not
claim unrestricted production live execution.

```sh
zeus provider-live-api --scenario status --json
ZEUS_RC2_PROVIDER_KEY=provider-rc2-material-value zeus provider-live-api --scenario loopback-smoke --secret-ref env://ZEUS_RC2_PROVIDER_KEY --json
zeus mcp-live-server --scenario status --json
ZEUS_RC3_MCP_TOKEN=mcp-rc3-token-value zeus mcp-live-server --scenario loopback-smoke --secret-ref env://ZEUS_RC3_MCP_TOKEN --json
zeus mcp-live-server --scenario prompt-injection-scan --json
zeus gateway-live-delivery --scenario status --json
ZEUS_RC4_GATEWAY_TOKEN=local-fixture-value zeus gateway-live-delivery --scenario loopback-smoke --secret-ref env://ZEUS_RC4_GATEWAY_TOKEN --json
ZEUS_RC4_GATEWAY_TOKEN=local-fixture-value zeus gateway-live-delivery --scenario blocked-target --target discord://ops --secret-ref env://ZEUS_RC4_GATEWAY_TOKEN --json
zeus sandbox-terminal-live --scenario local-smoke --json
zeus sandbox-terminal-live --scenario blocked-network --json
zeus sandbox-terminal-live --scenario blocked-remote --json
zeus memory-privacy-live --scenario local-smoke --json
zeus memory-privacy-live --scenario secret-quarantine --json
zeus memory-privacy-live --scenario delete-retention --json
zeus memory-privacy-live --scenario promotion-block --json
```

## Repository Layout

```text
src/zeus_agent/
  kernel/                         authority, capability graph, broker, evidence
  objective_runtime/              objective contracts and compiler
  model_runtime/                  provider interfaces and local/API-compatible adapters
  tool_runtime/                   tool schema registry and dispatch boundaries
  runtime_lease/                  dry-run/live lease and promotion controls
  goal_intelligence_runtime/      intent frames, interviews, work-loop bridge
  cognitive_provider_activation_runtime/
                                  provider-backed intent-frame activation
  productized_zeus_platform_runtime/
                                  product-facing persona, setup, cockpit, boundary
  memory_ontology_surface_runtime/
                                  local MemoryGraph, LLM Wiki, ontology review surface
  real_*_runtime/                 governed local product/runtime boundaries
tests/                            public deterministic scenario and contract tests
docs/                             public architecture and comparison notes
```
