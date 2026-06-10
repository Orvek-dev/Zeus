"""Capability registry overlay: cost, trust, and effect metadata.

Sits above the minimal kernel ``CapabilityDescriptor``. Domain knowledge enters
here only as machine-readable metadata (verb class, side effect, cost model),
filled by code review for builtins and by conservative, fail-closed defaults for
imported MCP tools. Trust is earned from ledger evidence, never granted by
default; a changed MCP schema re-quarantines the capability.
"""

from __future__ import annotations

from .models import (
    CapabilityRecord,
    CapabilityStatus,
    CapabilityTrust,
    CatalogEntry,
    CostConfidence,
    CostModel,
    Provenance,
    SideEffectClass,
    VerbClass,
)
from .registry import (
    catalog_entry,
    estimate_cost_units,
    evaluate_promotion,
    import_mcp_capability,
    recompute_trust,
    reconcile_schema,
    synthesis_catalog,
)
from .store import CapabilityStore

__all__ = [
    "CapabilityRecord",
    "CapabilityStore",
    "CapabilityStatus",
    "CapabilityTrust",
    "CatalogEntry",
    "CostConfidence",
    "CostModel",
    "Provenance",
    "SideEffectClass",
    "VerbClass",
    "catalog_entry",
    "estimate_cost_units",
    "evaluate_promotion",
    "import_mcp_capability",
    "recompute_trust",
    "reconcile_schema",
    "synthesis_catalog",
]
