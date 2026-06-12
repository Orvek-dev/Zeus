# Legacy Wave Attic

This directory contains the pre-control-plane wave-era CLI, eval, scenario,
and test artifacts.

It is intentionally outside the public product surface:

- not imported by `zeus`
- not packaged as an active product API
- not collected by the default `.venv/bin/python -m pytest`
- not counted in public release evidence

Use it only as historical reference while comparing the old agent-platform
harness against the current governance control plane. If behavior is promoted
back into the product, move only the needed implementation into `src/zeus_agent`
with new product-facing names and core/conformance tests.
