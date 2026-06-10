"""Assembled spine (integration): frame → card → executor → evidence.

The single runtime that wires the previously-islanded components into one
governed path. ``compile_and_run`` compiles the objective card and, if it is
ready to start, runs it through the WorkflowExecutionRuntime; ``resume`` advances
a suspended run past an approved gate. This is what makes "the spine is real"
true end-to-end, not just per-component.
"""

from __future__ import annotations

from .models import GovernedObjectiveResult
from .orchestrator import GovernedObjectiveOrchestrator

__all__ = ["GovernedObjectiveOrchestrator", "GovernedObjectiveResult"]
