# Security Policy

Zeus is a local-first governance control plane. The host agent executes its
own tools; Zeus decides, records, approves, and blocks at the gates.

## Defaults

- No remote telemetry is enabled by the package.
- Local runtime state (`~/.zeus/control-plane`: ledger, trust counts, grants,
  taint, queue) stays outside source control.
- Provider credentials stay on the host side; the proxy forwards auth headers
  and never persists them. The credential broker injects key material only at
  the egress point, on an allowed decision — agents hold references, not keys.
- Secret-looking values are redacted before they reach the ledger; the memory
  gate stores candidates redacted (poisoned candidates keep only a hash and a
  redacted preview), verified by a byte-level storage test.
- The `/zeus` decision API requires HMAC pairing and is never zero-confirm. A
  non-loopback `/v1` bind refuses to start without issued tokens
  (`zeus pair --issue-v1-token`, TTL + revocation) or an explicit unsafe flag;
  a valid token's registration — not spoofable headers — decides identity.
- Approvals are TTL fail-closed end to end: an expired parked action can never
  resolve as approved, and a burned "once" grant stays burned for every later
  process at every gate.

## Current v1.0.0-alpha Boundary

The final action returned to a host always equals the final decision receipt
in the hash-chained ledger (the receipt-coherence contract), and 88 frozen
conformance scenarios cover the four gates, governance UX, loop governance,
host adapters, hygiene modes, and remote safety.

That conformance is **synthetic** — contracts frozen against simulated hosts.
This alpha does not claim: validated parity with a pinned real hermes-agent or
OpenClaw build (those gate `v2.0.0` / `v3.0.0`, each requiring ≥95% plus a
7-day zero-bypass soak measured by instrumentation outside Zeus), OS-level
egress enforcement (the ring decides in-process and emits sandbox-runtime
profiles; the srt wrapper is the next milestone), hosted SaaS readiness,
browser automation, unattended production operation, or third-party
production validation. Cognition organs (memory write gate, skill quarantine)
are default-OFF.

## Reporting

Please report security issues privately before public disclosure.
