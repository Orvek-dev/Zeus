"""Runtime backend abstraction.

Hermes supports many execution backends. Zeus exposes the same architectural
slot, but defaults to the local approved sandbox and treats remote/container
backends as explicit policy boundaries until configured.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from zeus_agent.runtime.sandbox import SandboxRuntime
from zeus_agent.schemas.sandbox import SandboxResult


@dataclass(frozen=True)
class RuntimeBackendInfo:
    name: str
    isolation: str
    available: bool
    requires_network: bool
    requires_approval: bool
    notes: str


class RuntimeBackend(Protocol):
    info: RuntimeBackendInfo

    def run(self, run_id: str, argv: list[str], *, home: Path | None = None, timeout_seconds: int | None = None) -> SandboxResult:
        ...


class LocalProcessBackend:
    info = RuntimeBackendInfo(
        name="local-process",
        isolation="process",
        available=True,
        requires_network=False,
        requires_approval=True,
        notes="Approval-gated local process sandbox with scrubbed environment and Mneme evidence.",
    )

    def run(self, run_id: str, argv: list[str], *, home: Path | None = None, timeout_seconds: int | None = None) -> SandboxResult:
        return SandboxRuntime(home).run_command(run_id, argv, timeout_seconds=timeout_seconds)


class PolicyStubBackend:
    def __init__(self, name: str, isolation: str, *, requires_network: bool) -> None:
        self.info = RuntimeBackendInfo(
            name=name,
            isolation=isolation,
            available=False,
            requires_network=requires_network,
            requires_approval=True,
            notes="Registered architecture slot only; execution is blocked until a secure adapter is configured.",
        )

    def run(self, run_id: str, argv: list[str], *, home: Path | None = None, timeout_seconds: int | None = None) -> SandboxResult:
        raise RuntimeError(f"runtime backend {self.info.name} is not configured")


class RuntimeBackendRegistry:
    def __init__(self) -> None:
        self._backends: dict[str, RuntimeBackend] = {
            "local-process": LocalProcessBackend(),
            "docker": PolicyStubBackend("docker", "container", requires_network=False),
            "ssh": PolicyStubBackend("ssh", "remote", requires_network=True),
            "modal": PolicyStubBackend("modal", "remote-container", requires_network=True),
            "daytona": PolicyStubBackend("daytona", "remote-workspace", requires_network=True),
            "singularity": PolicyStubBackend("singularity", "container", requires_network=False),
            "microvm": PolicyStubBackend("microvm", "microvm", requires_network=False),
        }

    def list(self) -> list[RuntimeBackendInfo]:
        return [backend.info for backend in self._backends.values()]

    def get(self, name: str) -> RuntimeBackend:
        if name not in self._backends:
            raise KeyError(f"unknown runtime backend: {name}")
        return self._backends[name]


DEFAULT_RUNTIME_BACKENDS = RuntimeBackendRegistry()

