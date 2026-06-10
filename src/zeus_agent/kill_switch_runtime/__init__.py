"""Live kill switch (M5 / C3-ops) — instant halt + revoke.

A platform that runs live work is not safe without an immediate stop. The kill
switch is consulted by the execution runtime before every node: a global engage,
a per-run revoke, or a per-capability revoke blocks further side effects at once.
"""

from __future__ import annotations

from .switch import KillSwitch, RevocationReceipt

__all__ = ["KillSwitch", "RevocationReceipt"]
