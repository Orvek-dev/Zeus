"""Zeus launch screen (M5) — the locked terminal-native welcome.

Structured content + a plain-text render of the `zeus` first screen: the
gradient wordmark concept reduced to ANSI-renderable content, the three pillars
(objective / authority / evidence), honest status (mode, live), slash commands,
and the objective-first prompt. The design lives in docs; this renders it.
"""

from __future__ import annotations

from .screen import WelcomeScreen, build_welcome, render_text

__all__ = ["WelcomeScreen", "build_welcome", "render_text"]
