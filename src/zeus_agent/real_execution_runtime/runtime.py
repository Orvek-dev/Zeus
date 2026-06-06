from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Final, Optional

from zeus_agent.browser_runtime import BrowserDispatchFacade, BrowserDispatchRequest
from zeus_agent.real_execution_runtime.models import RealExecutionContract
from zeus_agent.real_execution_runtime.models import RealExecutionDecision
from zeus_agent.real_execution_runtime.models import RealExecutionScenario
from zeus_agent.sandbox_terminal_live_runtime import build_sandbox_terminal_live_contract
from zeus_agent.sandbox_runtime import SandboxDispatchFacade, SandboxDispatchRequest
from zeus_agent.terminal_runtime import TerminalDispatchFacade, TerminalDispatchRequest

_TARGET_VERSION: Final = "v1.4.0"
_OBJECTIVE_CONTRACT_ID: Final = "zeus.v1.4.0.browser_terminal_sandbox_execution"
_SUPPORTED_SCENARIOS: Final[frozenset[str]] = frozenset(
    {
        "status",
        "local-execution-smoke",
        "browser-blocked-live",
        "blocked-network",
        "blocked-remote",
    },
)


def build_real_execution_contract(
    *,
    scenario: str = "status",
    home: Optional[Path] = None,
    command: str = "pwd",
) -> RealExecutionContract:
    safe_scenario = scenario.strip()
    if safe_scenario not in _SUPPORTED_SCENARIOS:
        return _contract(
            decision="blocked",
            scenario="status",
            blocked_reasons=("unsupported_real_execution_scenario",),
        )
    parsed_scenario = _parse_scenario(safe_scenario)
    if parsed_scenario == "status":
        return _contract(decision="report", scenario="status")
    if parsed_scenario == "local-execution-smoke":
        return _local_execution_smoke(home=home, command=command)
    if parsed_scenario == "browser-blocked-live":
        return _browser_blocked_live()
    if parsed_scenario == "blocked-network":
        return _blocked_network(home=home)
    return _blocked_remote(home=home)


def _local_execution_smoke(*, home: Optional[Path], command: str) -> RealExecutionContract:
    preflight_block = _blocked_local_command_preflight(home=home, command=command)
    if preflight_block is not None:
        return preflight_block
    contract = build_sandbox_terminal_live_contract(
        scenario="local-smoke",
        home=home,
        command=command,
    )
    payload = contract.to_payload()
    ready = (
        payload["decision"] == "report"
        and payload["local_sandbox_execution_ready"] is True
        and payload["local_process_executed"] is True
        and payload["network_opened"] is False
        and payload["cleanup_performed"] is True
        and payload["no_secret_echo"] is True
    )
    return _contract(
        decision="report" if ready else "blocked",
        scenario="local-execution-smoke",
        blocked_reasons=() if ready else tuple(str(reason) for reason in payload["blocked_reasons"]),
        sandbox_terminal_contract=payload,
        local_terminal_smoke_ready=ready,
        sandbox_command_smoke_ready=ready,
        real_execution_runtime_ready=ready,
        controlled_local_side_effects=bool(payload["controlled_local_side_effects"]),
        handler_executed=bool(payload["handler_executed"]),
        local_process_executed=bool(payload["local_process_executed"]),
        fixture_file_write_performed=True,
        cleanup_performed=bool(payload["cleanup_performed"]),
        network_opened=bool(payload["network_opened"]),
    )


def _blocked_local_command_preflight(*, home: Optional[Path], command: str) -> Optional[RealExecutionContract]:
    with _temporary_sandbox(home) as raw_root:
        root = Path(raw_root)
        terminal_plan = TerminalDispatchFacade().plan(
            TerminalDispatchRequest(
                request_id="v140.terminal.local.preflight",
                command=command,
                root=root,
                evidence_target="mneme.v140.terminal",
            ),
        )
        sandbox_plan = SandboxDispatchFacade().plan(
            SandboxDispatchRequest(
                request_id="v140.sandbox.local.preflight",
                backend="local",
                root=root,
                mounts=(".",),
                commands=(command,),
                cleanup_required=True,
                cleanup_plan="temporary sandbox directory removed after evidence capture",
                evidence_target="mneme.v140.sandbox",
            ),
        )
    if terminal_plan.decision == "planned" and sandbox_plan.decision == "planned":
        return None
    return _contract(
        decision="blocked",
        scenario="local-execution-smoke",
        blocked_reasons=_unique(
            [
                terminal_plan.reason if terminal_plan.decision == "blocked" else None,
                *sandbox_plan.blocked_reasons,
            ],
        ),
        real_execution_runtime_ready=True,
        cleanup_performed=True,
    )


def _browser_blocked_live() -> RealExecutionContract:
    guard = BrowserDispatchFacade().plan(
        BrowserDispatchRequest(
            request_id="v140.browser.live.guard",
            target_url="https://example.test/v140",
            dry_run=False,
            network_host="example.test",
            approval_receipt_id="approval://v140/browser",
            evidence_target="mneme.v140.browser",
        ),
    )
    payload = guard.model_dump(mode="json")
    ready = (
        guard.decision == "blocked"
        and guard.network_opened is False
        and guard.handler_executed is False
        and "live_navigation_not_supported" in guard.blocked_reasons
    )
    return _contract(
        decision="blocked",
        scenario="browser-blocked-live",
        blocked_reasons=tuple(str(reason) for reason in guard.blocked_reasons),
        browser_guard=payload,
        browser_live_guard_ready=ready,
        real_execution_runtime_ready=ready,
    )


def _blocked_network(*, home: Optional[Path]) -> RealExecutionContract:
    contract = build_sandbox_terminal_live_contract(scenario="blocked-network", home=home)
    payload = contract.to_payload()
    ready = (
        payload["decision"] == "blocked"
        and payload["network_opened"] is False
        and payload["no_secret_echo"] is True
    )
    return _contract(
        decision="blocked",
        scenario="blocked-network",
        blocked_reasons=tuple(str(reason) for reason in payload["blocked_reasons"]),
        sandbox_terminal_contract=payload,
        network_block_ready=ready,
        real_execution_runtime_ready=ready,
        cleanup_performed=bool(payload["cleanup_performed"]),
        network_opened=bool(payload["network_opened"]),
    )


def _blocked_remote(*, home: Optional[Path]) -> RealExecutionContract:
    contract = build_sandbox_terminal_live_contract(scenario="blocked-remote", home=home)
    payload = contract.to_payload()
    ready = (
        payload["decision"] == "blocked"
        and payload["remote_execution_opened"] is False
        and payload["network_opened"] is False
        and payload["cleanup_performed"] is True
        and payload["no_secret_echo"] is True
        and "missing_cleanup_obligation" not in payload["blocked_reasons"]
    )
    return _contract(
        decision="blocked",
        scenario="blocked-remote",
        blocked_reasons=tuple(str(reason) for reason in payload["blocked_reasons"]),
        sandbox_terminal_contract=payload,
        remote_sandbox_block_ready=ready,
        real_execution_runtime_ready=ready,
        cleanup_performed=bool(payload["cleanup_performed"]),
        network_opened=bool(payload["network_opened"]),
        remote_execution_opened=bool(payload["remote_execution_opened"]),
    )


def _contract(
    *,
    decision: RealExecutionDecision,
    scenario: RealExecutionScenario,
    blocked_reasons: tuple[str, ...] = (),
    sandbox_terminal_contract: Optional[dict] = None,
    browser_guard: Optional[dict] = None,
    local_terminal_smoke_ready: bool = False,
    sandbox_command_smoke_ready: bool = False,
    browser_live_guard_ready: bool = False,
    network_block_ready: bool = False,
    remote_sandbox_block_ready: bool = False,
    real_execution_runtime_ready: bool = False,
    controlled_local_side_effects: bool = False,
    handler_executed: bool = False,
    local_process_executed: bool = False,
    fixture_file_write_performed: bool = False,
    cleanup_performed: bool = False,
    network_opened: bool = False,
    remote_execution_opened: bool = False,
) -> RealExecutionContract:
    return RealExecutionContract(
        decision=decision,
        target_version=_TARGET_VERSION,
        release_stage="browser_terminal_sandbox_execution",
        objective_contract_id=_OBJECTIVE_CONTRACT_ID,
        scenario=scenario,
        blocked_reasons=blocked_reasons,
        local_terminal_smoke_ready=local_terminal_smoke_ready,
        sandbox_command_smoke_ready=sandbox_command_smoke_ready,
        browser_live_guard_ready=browser_live_guard_ready,
        network_block_ready=network_block_ready,
        remote_sandbox_block_ready=remote_sandbox_block_ready,
        real_execution_runtime_ready=real_execution_runtime_ready,
        production_ready=False,
        sandbox_terminal_contract=sandbox_terminal_contract,
        browser_guard=browser_guard,
        network_opened=network_opened,
        non_loopback_network_opened=False,
        controlled_local_side_effects=controlled_local_side_effects,
        handler_executed=handler_executed,
        local_process_executed=local_process_executed,
        fixture_file_write_performed=fixture_file_write_performed,
        file_write_executed=False,
        cleanup_performed=cleanup_performed,
        credential_material_accessed=False,
        external_delivery_opened=False,
        remote_execution_opened=remote_execution_opened,
        raw_secret_returned=False,
        live_production_claimed=False,
    ).with_secret_scan()


def _parse_scenario(value: str) -> RealExecutionScenario:
    if value == "status":
        return "status"
    if value == "local-execution-smoke":
        return "local-execution-smoke"
    if value == "browser-blocked-live":
        return "browser-blocked-live"
    if value == "blocked-network":
        return "blocked-network"
    return "blocked-remote"


def _temporary_sandbox(home: Optional[Path]):
    if home is not None:
        home.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix="zeus-v140-preflight-", dir=home.as_posix())
    return tempfile.TemporaryDirectory(prefix="zeus-v140-preflight-")


def _unique(values) -> tuple[str, ...]:
    reasons: list[str] = []
    for value in values:
        if value and value not in reasons:
            reasons.append(str(value))
    return tuple(reasons)
