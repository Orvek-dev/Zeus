from __future__ import annotations



from pydantic import BaseModel, ConfigDict, JsonValue


class SurfaceStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    surface: str
    ready: bool
    detail: str


class StatusReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    surfaces: tuple[SurfaceStatus, ...]
    ready_count: int
    blocked_count: int
    production_live_claimed: bool = False

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


def build_status(surfaces: tuple[SurfaceStatus, ...]) -> StatusReport:
    """Aggregate surface readiness. ``production_live_claimed`` stays False unless
    EVERY surface is ready — Zeus never overstates what it can do."""
    ready = sum(1 for s in surfaces if s.ready)
    blocked = sum(1 for s in surfaces if not s.ready)
    return StatusReport(
        surfaces=surfaces,
        ready_count=ready,
        blocked_count=blocked,
        production_live_claimed=blocked == 0 and len(surfaces) > 0,
    )
