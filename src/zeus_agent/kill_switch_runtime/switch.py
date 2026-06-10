from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class RevocationReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    scope: str  # global | run | capability
    target: Optional[str] = None
    reason: str


class KillSwitch:
    """In-memory revocation registry. The execution runtime consults
    ``is_blocked`` before every node, so engaging the switch halts in-flight work
    at the next step rather than waiting for it to finish."""

    def __init__(self) -> None:
        self._global = False
        self._runs: set[str] = set()
        self._capabilities: set[str] = set()
        self._receipts: list[RevocationReceipt] = []

    def engage_global(self, *, reason: str = "operator_kill") -> RevocationReceipt:
        self._global = True
        return self._record(RevocationReceipt(scope="global", reason=reason))

    def release_global(self) -> None:
        self._global = False

    def revoke_run(self, run_id: str, *, reason: str = "operator_revoke") -> RevocationReceipt:
        self._runs.add(run_id)
        return self._record(RevocationReceipt(scope="run", target=run_id, reason=reason))

    def revoke_capability(self, capability_id: str, *, reason: str = "operator_revoke") -> RevocationReceipt:
        self._capabilities.add(capability_id)
        return self._record(RevocationReceipt(scope="capability", target=capability_id, reason=reason))

    def is_blocked(
        self,
        *,
        run_id: Optional[str] = None,
        capability_id: Optional[str] = None,
    ) -> Optional[str]:
        if self._global:
            return "kill_switch_global"
        if run_id is not None and run_id in self._runs:
            return "run_revoked"
        if capability_id is not None and capability_id in self._capabilities:
            return "capability_revoked"
        return None

    def receipts(self) -> tuple[RevocationReceipt, ...]:
        return tuple(self._receipts)

    def _record(self, receipt: RevocationReceipt) -> RevocationReceipt:
        self._receipts.append(receipt)
        return receipt
