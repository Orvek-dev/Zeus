"""ACS-manifest read compatibility (P0).

Zeus rides external agent-capability-spec manifests instead of fighting them:
a thin loader maps their interception points onto Zeus capability ids so a
host that already ships an ACS manifest can plug into the Decision API
without re-describing its tools.
"""

from __future__ import annotations

from .loader import AcsInterception, AcsManifest, capability_map, load_acs_manifest

__all__ = ["AcsInterception", "AcsManifest", "capability_map", "load_acs_manifest"]
