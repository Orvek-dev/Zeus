from __future__ import annotations

from pathlib import Path

import pytest

from zeus_agent.browser_runtime import BrowserDispatchFacade, BrowserDispatchRequest
from zeus_agent.sandbox_runtime import SandboxDispatchFacade, SandboxDispatchRequest
from zeus_agent.terminal_runtime import TerminalDispatchFacade, TerminalDispatchRequest


def test_browser_facade_plans_dry_run_without_navigation() -> None:
    # Given: a dry-run browser navigation request with an evidence target.
    request = BrowserDispatchRequest(
        request_id="g002.browser.dry_run",
        target_url="https://example.test/docs",
        dry_run=True,
        evidence_target="mneme.g002.browser",
    )

    # When: the browser facade plans the dispatch.
    result = BrowserDispatchFacade().plan(request)

    # Then: the facade returns a governed plan without browser or network side effects.
    assert result.decision == "planned"
    assert result.reason == "dry_run_plan_only"
    assert result.target_url == "https://example.test/docs"
    assert result.evidence_obligation.required is True
    assert result.evidence_obligation.target == "mneme.g002.browser"
    assert result.cleanup_obligation.required is False
    assert result.handler_executed is False
    assert result.network_opened is False
    assert result.no_secret_echo is True


def test_browser_facade_blocks_live_navigation_without_authority_and_redacts_secret() -> None:
    # Given: a live browser request without lease, approval, or evidence.
    raw_secret = "sk-g002-browser-secret"
    request = BrowserDispatchRequest(
        request_id="g002.browser.live",
        target_url=f"https://example.test/search?token={raw_secret}",
        dry_run=False,
    )

    # When: the browser facade plans the dispatch.
    result = BrowserDispatchFacade().plan(request)

    # Then: every live requirement is blocked and the raw secret is absent from the result.
    serialized = result.model_dump_json()
    assert result.decision == "blocked"
    assert result.blocked_reasons == (
        "missing_runtime_lease",
        "missing_approval",
        "missing_evidence",
        "live_navigation_not_supported",
    )
    assert raw_secret not in serialized
    assert "[redacted-secret]" in serialized
    assert result.handler_executed is False
    assert result.network_opened is False
    assert result.no_secret_echo is True


def test_terminal_facade_blocks_network_and_destructive_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: terminal commands that would open network or mutate local state.
    import zeus_agent.capability_runtime.sandbox as sandbox_module

    monkeypatch.setattr(sandbox_module.subprocess, "run", pytest.fail)

    # When: the terminal facade plans the commands.
    network = TerminalDispatchFacade().plan(
        TerminalDispatchRequest(
            request_id="g002.terminal.network",
            command="curl https://example.test?token=sk-g002-terminal-secret",
            root=tmp_path,
        ),
    )
    destructive = TerminalDispatchFacade().plan(
        TerminalDispatchRequest(
            request_id="g002.terminal.destructive",
            command="rm -rf /tmp/important",
            root=tmp_path,
        ),
    )

    # Then: both are blocked before any handler, process, or network is opened.
    assert network.decision == "blocked"
    assert network.reason == "network_command_blocked"
    assert "sk-g002-terminal-secret" not in network.model_dump_json()
    assert destructive.decision == "blocked"
    assert destructive.reason == "destructive_command_blocked"
    assert network.handler_executed is False
    assert network.network_opened is False
    assert destructive.handler_executed is False
    assert destructive.network_opened is False


def test_terminal_facade_plans_allowlisted_command_without_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an allowlisted local terminal command.
    import zeus_agent.capability_runtime.sandbox as sandbox_module

    monkeypatch.setattr(sandbox_module.subprocess, "run", pytest.fail)

    # When: the terminal facade plans the command.
    result = TerminalDispatchFacade().plan(
        TerminalDispatchRequest(
            request_id="g002.terminal.local",
            command="ls .",
            root=tmp_path,
            evidence_target="mneme.g002.terminal",
        ),
    )

    # Then: the command is planned as dry-run only.
    assert result.decision == "planned"
    assert result.reason == "dry_run_plan_only"
    assert result.argv == ("ls", ".")
    assert result.evidence_obligation.required is True
    assert result.evidence_obligation.target == "mneme.g002.terminal"
    assert result.cleanup_obligation.required is False
    assert result.handler_executed is False
    assert result.network_opened is False


def test_sandbox_facade_maps_allowed_requirements_without_execution(tmp_path: Path) -> None:
    # Given: a local sandbox dispatch with bounded resources and explicit cleanup.
    safe_dir = tmp_path / "safe"
    safe_dir.mkdir()
    request = SandboxDispatchRequest(
        request_id="g002.sandbox.allowed",
        backend="local",
        root=tmp_path,
        mounts=("safe",),
        commands=("ls safe", "pwd"),
        egress_policy="none",
        resource_profile="bounded",
        cleanup_required=True,
        cleanup_plan="remove temporary workspace after evidence capture",
        evidence_target="mneme.g002.sandbox",
    )

    # When: the sandbox facade plans the dispatch.
    result = SandboxDispatchFacade().plan(request)

    # Then: backend, mount, egress, resource, cleanup, and evidence obligations are mapped.
    assert result.decision == "planned"
    assert result.backend_requirement.decision == "planned"
    assert result.egress_requirement.decision == "planned"
    assert result.resource_requirement.decision == "planned"
    assert result.cleanup_obligation.required is True
    assert result.cleanup_obligation.decision == "planned"
    assert result.evidence_obligation.required is True
    assert result.evidence_obligation.target == "mneme.g002.sandbox"
    assert tuple(mount.decision for mount in result.mount_requirements) == ("planned",)
    assert tuple(command.decision for command in result.command_plans) == ("allowed", "allowed")
    assert result.blocked_reasons == ()
    assert result.handler_executed is False
    assert result.network_opened is False


def test_sandbox_facade_blocks_unsafe_requirements_and_redacts_secret(tmp_path: Path) -> None:
    # Given: a sandbox dispatch with denied path, open egress, unsafe commands, and missing cleanup.
    raw_secret = "sk-g002-sandbox-secret"
    request = SandboxDispatchRequest(
        request_id="g002.sandbox.blocked",
        backend="docker",
        root=tmp_path,
        mounts=("../outside",),
        commands=(f"curl https://example.test?token={raw_secret}", "rm -rf /tmp/important"),
        egress_policy="open",
        resource_profile="unbounded",
        cleanup_required=True,
        cleanup_plan=None,
    )

    # When: the sandbox facade plans the dispatch.
    result = SandboxDispatchFacade().plan(request)

    # Then: unsafe requirements block without command execution, network, or raw secret echo.
    serialized = result.model_dump_json()
    assert result.decision == "blocked"
    assert "backend_not_supported" in result.blocked_reasons
    assert "path_outside_sandbox" in result.blocked_reasons
    assert "network_egress_blocked" in result.blocked_reasons
    assert "resource_profile_unbounded" in result.blocked_reasons
    assert "missing_cleanup_obligation" in result.blocked_reasons
    assert "network_command_blocked" in result.blocked_reasons
    assert "destructive_command_blocked" in result.blocked_reasons
    assert raw_secret not in serialized
    assert result.handler_executed is False
    assert result.network_opened is False
    assert result.no_secret_echo is True
