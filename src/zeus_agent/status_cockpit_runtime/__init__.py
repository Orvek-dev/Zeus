"""Honest status cockpit (M5).

States plainly what Zeus can do now vs what is still blocked — evidence over
confidence, rendered as product. Each surface reports ready/blocked with an
honest reason, and the cockpit never claims production-live readiness it cannot
back with evidence.
"""

from __future__ import annotations

from .cockpit import SurfaceStatus, StatusReport, build_status

__all__ = ["StatusReport", "SurfaceStatus", "build_status"]
