from __future__ import annotations

from pathlib import PurePosixPath
from typing import Final, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from zeus_agent.decision_api_runtime import (
    DecisionContext,
    DecisionRequest,
    GateSurface,
    HostKind,
    ZeusDecisionEngine,
)
from zeus_agent.trust_loop_runtime import (
    ExecutionOutcome,
    ExecutionStatus,
    TrustDecision,
)

_RELEASED: Final = {TrustDecision.AUTO, TrustDecision.NOTIFY}


class EgressRing(BaseModel):
    """The hard boundary: hosts and directories. Not a judgement — a wall.

    Policy decides WITHIN the ring; nothing policy says can reach outside it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    allowed_hosts: tuple[str, ...] = ()
    allowed_dirs: tuple[str, ...] = ()
    blocked_dirs: tuple[str, ...] = Field(
        default=("~/.ssh", "~/.aws", "~/.gnupg", "/etc"),
    )

    def host_allowed(self, host: str) -> bool:
        target = host.strip().lower()
        for allowed in self.allowed_hosts:
            candidate = allowed.strip().lower()
            if target == candidate or target.endswith("." + candidate):
                return True
        return False

    def path_allowed(self, path: str, *, home: str = "/Users/agent") -> bool:
        target = PurePosixPath(path.replace("~", home))
        for blocked in self.blocked_dirs:
            if _contains(PurePosixPath(blocked.replace("~", home)), target):
                return False
        if not self.allowed_dirs:
            return False  # no ring configured → nothing is in scope (fail closed)
        return any(
            _contains(PurePosixPath(allowed.replace("~", home)), target)
            for allowed in self.allowed_dirs
        )


class CredentialVault(Protocol):
    def resolve(self, ref: str) -> Optional[str]: ...


class StaticVault:
    """Reference vault: refs → secrets, resolution counted for the tests that
    prove a denied egress never touches key material."""

    def __init__(self, secrets: dict[str, str]) -> None:
        self._secrets = dict(secrets)
        self.resolutions = 0

    def resolve(self, ref: str) -> Optional[str]:
        self.resolutions += 1
        return self._secrets.get(ref)


class EgressRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    session_id: str = "egress.default"
    principal_id: str = "agent.egress"
    objective_id: Optional[str] = None
    host: HostKind = HostKind.console
    network_host: Optional[str] = None
    path: Optional[str] = None
    write: bool = False
    credential_ref: Optional[str] = None

    def run_id(self) -> str:
        cleaned = "".join(ch for ch in self.session_id if ch.isalnum())
        return "run.egress.{0}".format((cleaned[:12] or "default").lower())


class EgressResult(BaseModel):
    """What the AGENT sees. Injected credentials never appear here — the
    transport headers live only on the Zeus side of the boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    allowed: bool
    reason: str
    receipt_id: Optional[str] = None
    credential_injected: bool = False


class EgressGate:
    """decide() then enforce the ring — in that order on the record, but the
    ring wins: an allowed decision outside the ring is still a deny."""

    def __init__(
        self,
        *,
        engine: ZeusDecisionEngine,
        ring: EgressRing,
        vault: Optional[CredentialVault] = None,
        home: str = "/Users/agent",
    ) -> None:
        self.engine = engine
        self.ring = ring
        self.vault = vault
        self.home = home
        # the gate guarantees its own surface vocabulary: a connect INSIDE the
        # ring is a read-class act (the ring + taint rules carry the risk) —
        # without this, the conservative fallback would ask on every connect.
        if engine.capabilities.get("net.connect") is None:
            engine.capabilities.register(_net_connect_record())
        # ring hosts are operator-approved by construction: exempt from novelty
        novelty = getattr(engine.governors, "novelty", None)
        if novelty is not None:
            for host in ring.allowed_hosts:
                novelty.learn("network_host", host.strip().lower())

    def connect(self, request: EgressRequest) -> tuple[EgressResult, dict[str, str]]:
        """Network egress. Returns (agent-visible result, transport headers).
        The headers — including any injected credential — stay Zeus-side."""
        host = (request.network_host or "").strip()
        if not host:
            return EgressResult(allowed=False, reason="egress_host_missing"), {}
        capability_id = "net.connect"
        # The ring is a WALL, not a judgement: a host outside it is a boundary
        # violation fed INTO decide() so the receipt records the DENY itself —
        # never a dangling AUTO receipt the gate quietly overrides afterward.
        # NOTE: the credential ref is NOT a decision arg — the agent never
        # touched key material (that is the broker's whole point); the
        # injection itself is recorded as the execution outcome below.
        boundary = None if self.ring.host_allowed(host) else "egress_host_not_allowed"
        response = self._decide(request, capability_id, {"network_host": host}, boundary=boundary)
        self._observe(request, capability_id, response.receipt_id)
        if response.decision not in _RELEASED:
            return EgressResult(
                allowed=False, reason=response.reason, receipt_id=response.receipt_id
            ), {}
        headers: dict[str, str] = {}
        injected = False
        if request.credential_ref is not None and self.vault is not None:
            secret = self.vault.resolve(request.credential_ref)
            if secret is not None:
                headers["authorization"] = "Bearer {0}".format(secret)
                injected = True
        self.engine.record(
            response.receipt_id,
            ExecutionOutcome(
                status=ExecutionStatus.success,
                notes="egress connect {0}{1}".format(
                    host,
                    " credential_injected:{0}".format(request.credential_ref)
                    if injected
                    else "",
                ),
            ),
            capability_id=capability_id,
            session_id=request.session_id,
            objective_id=request.objective_id,
        )
        return (
            EgressResult(
                allowed=True,
                reason=response.reason,
                receipt_id=response.receipt_id,
                credential_injected=injected,
            ),
            headers,
        )

    def access_path(self, request: EgressRequest) -> EgressResult:
        """Filesystem ring. Out-of-ring is a boundary violation fed INTO
        decide(), so the single receipt is the truth — not a post-hoc deny."""
        path = (request.path or "").strip()
        if not path:
            return EgressResult(allowed=False, reason="egress_path_missing")
        capability_id = "fs.write" if request.write else "fs.read"
        boundary = (
            None if self.ring.path_allowed(path, home=self.home) else "egress_path_outside_ring"
        )
        response = self._decide(request, capability_id, {"path": path}, boundary=boundary)
        self._observe(request, capability_id, response.receipt_id)
        if response.decision not in _RELEASED:
            return EgressResult(
                allowed=False, reason=response.reason, receipt_id=response.receipt_id
            )
        return EgressResult(allowed=True, reason=response.reason, receipt_id=response.receipt_id)

    # ------------------------------------------------------------- internals
    def _decide(
        self,
        request: EgressRequest,
        capability_id: str,
        args: dict[str, JsonValue],
        *,
        boundary: Optional[str] = None,
    ):
        return self.engine.decide(
            DecisionRequest(
                principal_id=request.principal_id,
                session_id=request.session_id,
                run_id=request.run_id(),
                capability_id=capability_id,
                args=args,
                context=DecisionContext(
                    host=request.host,
                    surface=GateSurface.egress,
                    objective_id=request.objective_id,
                    boundary_violation=boundary,
                ),
            )
        )

    def _observe(self, request: EgressRequest, capability_id: str, receipt_id: str) -> None:
        self.engine.recorder.record_gate_observation(
            run_id=request.run_id(),
            host=request.host.value,
            surface=GateSurface.egress.value,
            capability_id=capability_id,
            governed=True,
            decision_receipt_record_id=receipt_id,
        )


def _net_connect_record():
    from zeus_agent.capability_registry_runtime import (
        CapabilityRecord,
        CapabilityStatus,
        CapabilityTrust,
        CostModel,
        Provenance,
        SideEffectClass,
        VerbClass,
    )
    from zeus_agent.trust_loop_runtime import Reversibility

    return CapabilityRecord(
        capability_id="net.connect",
        verb_class=VerbClass.fetch,
        title="Open a network connection inside the egress ring",
        input_summary="host (ring-checked)",
        output_summary="connection",
        side_effect=SideEffectClass.none,
        reversibility=Reversibility.reversible,
        cost_model=CostModel(),
        trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
        provenance=Provenance.builtin,
        status=CapabilityStatus.active,
    )


def _contains(parent: PurePosixPath, child: PurePosixPath) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return parent == child
