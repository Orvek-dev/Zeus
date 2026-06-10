# Third-Party Notices

Zeus is a local-first governance control plane that external agent platforms
plug into. It is designed to complement those platforms, and parts of its
design are inspired by — or planned to interoperate with — the projects below.
Zeus does not vendor their source code unless explicitly stated; notices are
listed both for attribution and so future adoption stays license-clean.

## hermes-agent

- Project: hermes-agent (agent platform; Zeus integrates via hooks, base_url
  proxy, and MCP gateway surfaces)
- License: MIT
- Use in Zeus: integration target (Gate adapters under `adapters/`), design
  inspiration for platform breadth. No source code vendored.

## OpenClaw

- Project: OpenClaw (agent platform; planned integration target for the
  baseUrl proxy, MCP gateway, and exec approval operator-client)
- License: MIT
- Use in Zeus: integration target and threat-model reference (capability
  quarantine and rug-pull reconciliation in `capability_registry_runtime`
  respond to attack classes observed in its plugin ecosystem). No source code
  vendored.

## tmux

- Project: tmux (terminal multiplexer)
- License: ISC
- Use in Zeus: planned terminal-session primitive for host adapters that need
  long-lived governed terminal sessions. Invoked as an external program; no
  source code vendored.

## srt (sandbox runtime)

- Project: Anthropic srt sandbox primitive
- License: Apache-2.0
- Use in Zeus: planned egress/filesystem sandbox primitive for Gate 4
  (`P8` in the roadmap: network egress allowlist, filesystem ring, credential
  injection at egress). No source code vendored yet; when adopted, the
  Apache-2.0 license and NOTICE obligations will be carried here.

## Claude Code

- Project: Claude Code (Anthropic CLI agent; Gate 0 host)
- Use in Zeus: Zeus ships a PreToolUse/PostToolUse hook adapter
  (`adapters/claude_code_hook`) that talks to Claude Code's documented hook
  interface. No Claude Code source code is included.

---

Python dependencies (pydantic, typer, rich) are used under their respective
licenses as declared in `pyproject.toml`.
