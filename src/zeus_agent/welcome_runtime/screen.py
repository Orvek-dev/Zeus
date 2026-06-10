from __future__ import annotations



from pydantic import BaseModel, ConfigDict, JsonValue

_TAGLINE = "governed objective runtime"
_DESCRIPTORS = ("objective-first", "authority-gated", "evidence-backed")
_SLASH = ("/objective", "/run", "/approve", "/evidence", "/tools", "/status", "/help")
_PROMPT_HINT = "describe an outcome in plain language…"


class WelcomeScreen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    version: str
    tagline: str
    descriptors: tuple[str, ...]
    pillars: tuple[tuple[str, str], ...]
    stats: tuple[tuple[str, str], ...]
    slash_commands: tuple[str, ...]
    prompt_hint: str
    mode: str
    live_connected: bool

    def to_payload(self) -> dict[str, JsonValue]:
        return self.model_dump(mode="json")


def build_welcome(
    *,
    version: str,
    model: str = "anthropic/claude-opus-4.8",
    session: str = "default",
    status: str = "ready",
    mode: str = "dry-run",
    live_connected: bool = False,
    objective: str = "no active objective",
    authority: str = "no active lease",
    evidence: str = "ledger ready · 0 receipts",
) -> WelcomeScreen:
    return WelcomeScreen(
        version=version,
        tagline=_TAGLINE,
        descriptors=_DESCRIPTORS,
        pillars=(("objective", objective), ("authority", authority), ("evidence", evidence)),
        stats=(
            ("model", model),
            ("session", session),
            ("tools", "approval-gated"),
            ("status", status),
            ("mode", mode),
            ("live", "connected" if live_connected else "not connected"),
        ),
        slash_commands=_SLASH,
        prompt_hint=_PROMPT_HINT,
        mode=mode,
        live_connected=live_connected,
    )


def render_text(screen: WelcomeScreen) -> str:
    """Plain monospace render — the same content a rich/ANSI front end colorizes."""
    lines: list[str] = []
    lines.append("ZEUS  {0}".format(screen.version))
    lines.append(screen.tagline + "  ·  " + " · ".join(screen.descriptors))
    lines.append("")
    for name, value in screen.pillars:
        lines.append("  {0:<10} {1}".format(name, value))
    lines.append("")
    for key, value in screen.stats:
        lines.append("  {0:<8} {1}".format(key, value))
    lines.append("")
    lines.append("  ".join(screen.slash_commands))
    lines.append("")
    lines.append("zeus › {0}".format(screen.prompt_hint))
    return "\n".join(lines)
