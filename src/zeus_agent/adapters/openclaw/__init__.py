"""OpenClaw adapter (P9).

OpenClaw has no pre-tool hook for non-exec tools, so the PRIMARY gate is the
LLM proxy (tool_calls intercepted in the response stream) plus the MCP
gateway. Exec is governed through the approval relay: Zeus subscribes to
``exec.approval.requested`` as an operator client, decides, and resolves —
allow, deny, or park-for-the-human. Self-onboarding ships as a ClawHub-style
``zeus-connect`` skill; pairing is still never zero-confirm.

NOTE: event field names target the OpenClaw gateway protocol pinned in the
design notes; re-verify on the pinned OpenClaw version at integration time.
"""

from __future__ import annotations

from .connect import openclaw_connect_bundle, zeus_connect_skill
from .relay import ExecApprovalRelay

__all__ = ["ExecApprovalRelay", "openclaw_connect_bundle", "zeus_connect_skill"]
