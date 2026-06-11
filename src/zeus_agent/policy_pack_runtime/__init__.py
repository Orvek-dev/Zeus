"""Policy packs (P6): declarative presets, governed like any other action.

A pack bundles budget, rate caps, quiet hours, and an explicit never-do lock
list. Applying (or changing) a pack is ITSELF a decision with a receipt —
governance of governance — and never happens without operator confirmation.
"""

from __future__ import annotations

from .packs import (
    BUILTIN_PACKS,
    PolicyPack,
    apply_pack,
    onboarding_pack,
    pack_by_name,
)

__all__ = ["BUILTIN_PACKS", "PolicyPack", "apply_pack", "onboarding_pack", "pack_by_name"]
