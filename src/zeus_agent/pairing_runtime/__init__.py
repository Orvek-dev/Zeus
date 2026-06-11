"""1-tap pairing — the root of trust between a host agent and zeusd (P5).

A policy-server swap is total compromise (CVE-2026-25253 class), so pairing
is NEVER zero-confirm: the agent requests a pairing, the human approves the
short code out-of-band (`zeus pair --approve CODE`), and only then do signed
requests verify. Requests are HMAC-signed with the pairing secret and a
timestamp, so a replayed or forged decide() never reaches policy.
"""

from __future__ import annotations

from .pairing import PairingManager, sign_request

__all__ = ["PairingManager", "sign_request"]
