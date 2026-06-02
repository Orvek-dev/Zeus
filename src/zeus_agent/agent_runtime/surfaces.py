from __future__ import annotations

from pathlib import Path
from typing import Final, Literal

from zeus_agent.capability_runtime import build_wave3_capability_graph, build_wave3_handlers
from zeus_agent.kernel.authority import AuthorityContext, CapabilityGrant, PathGrant
from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.kernel.completion import summarize_completion
from zeus_agent.kernel.contracts import GoalContract
from zeus_agent.model_runtime import FakeModelRuntime, ModelRequest, ModelResponse, ToolCall
from zeus_agent.model_runtime.fake import fake_tool_matrix
from zeus_agent.model_runtime.providers import ProviderRouteRequest, default_provider_router

WAVE3_SURFACE_REQ: Final = "REQ-ZEUS-WAVE3-005:S1"
PROFILE: Final = "coding-agent"
Mode = Literal["run", "chat"]


def run_wave3_surface(
    prompt: str,
    home: Path,
    scenario: str = "fake-read",
) -> dict[str, object]:
    return _execute_surface(mode="run", user_text=prompt, home=home, scenario=scenario)


def chat_wave3_surface(
    message: str,
    home: Path,
    scenario: str = "fake-search",
) -> dict[str, object]:
    return _execute_surface(mode="chat", user_text=message, home=home, scenario=scenario)


def _execute_surface(
    *,
    mode: Mode,
    user_text: str,
    home: Path,
    scenario: str,
) -> dict[str, object]:
    sandbox_root = _prepare_sandbox(home)
    contract = _contract(mode, scenario)
    authority = _authority(sandbox_root, contract)
    graph = build_wave3_capability_graph()
    broker = CapabilityBroker(graph=graph, handlers=build_wave3_handlers(sandbox_root))
    visible_tools = _visible_tool_names(graph.compile_model_schema(PROFILE, authority))
    route = default_provider_router().route(
        ProviderRouteRequest(
            provider="fake",
            required_tool_calling=True,
            required_json_mode=True,
            local_private=True,
            network_allowed=False,
        )
    )
    runtime = FakeModelRuntime(
        matrix=fake_tool_matrix(),
        responses=[
            ModelResponse(
                turn_id="wave3-{0}-tool".format(mode),
                content="requesting governed fake tool",
                tool_call=_tool_call(mode, scenario, sandbox_root),
            ),
            ModelResponse(
                turn_id="wave3-{0}-final".format(mode),
                content="evidence-derived completion ready",
            ),
        ],
    )
    request = ModelRequest(
        prompt_context=_prompt_context(mode, scenario, user_text, visible_tools),
        tool_schema=graph.compile_model_schema(PROFILE, authority),
    )
    first_turn = runtime.next_response(request)
    tool_call = first_turn.tool_call
    if tool_call is None:
        raise RuntimeError("Wave 3 fake runtime must emit a tool call")
    dispatch = broker.dispatch(
        capability_id=tool_call.capability_id,
        payload=tool_call.arguments,
        context=authority,
        profile=PROFILE,
        criterion_id=WAVE3_SURFACE_REQ,
    )
    completion = summarize_completion(contract, broker.evidence_records)
    final_turn = runtime.next_response(request) if completion.status == "complete" else None
    return {
        "mode": mode,
        "scenario": scenario,
        "fake_local_only": True,
        "state_home": str(home),
        "sandbox_root": str(sandbox_root),
        "runtime_metadata": {
            "provider": "fake",
            "local_only": True,
            "network_allowed": False,
            "credential_calls": False,
            "mcp_calls": False,
            "browser_calls": False,
        },
        "prompt_metadata": {"kind": "redacted", "length": len(user_text)},
        "provider_route": route.model_dump(mode="json"),
        "model_visible_capabilities": visible_tools,
        "model_turn": first_turn.model_dump(mode="json"),
        "tool_call": tool_call.model_dump(mode="json"),
        "broker_decision": dispatch,
        "completion": completion.model_dump(mode="json"),
        "final_turn": None if final_turn is None else final_turn.model_dump(mode="json"),
    }


def _prepare_sandbox(home: Path) -> Path:
    sandbox_root = home / "sandbox"
    sandbox_root.mkdir(parents=True, exist_ok=True)
    fixture = sandbox_root / "wave3.txt"
    fixture.write_text("wave3 fixture content\nneedle: wave3 searchable line\n", encoding="utf-8")
    return sandbox_root.resolve()


def _contract(mode: Mode, scenario: str) -> GoalContract:
    return GoalContract(
        goal_contract_id="wave3-{0}-{1}-goal".format(mode, scenario),
        raw_user_request="wave3 fake local {0}".format(mode),
        normalized_goal="execute fake governed Wave 3 {0} surface".format(mode),
        deliverables=["wave3 {0} surface".format(mode)],
        acceptance_criteria=[WAVE3_SURFACE_REQ],
    )


def _authority(root: Path, contract: GoalContract) -> AuthorityContext:
    return AuthorityContext(
        principal_id="wave3-surface-principal",
        run_id="wave3-surface-run",
        goal_contract_id=contract.goal_contract_id,
        capability_grants=[
            CapabilityGrant(capability_id="file.read"),
            CapabilityGrant(capability_id="text.search"),
        ],
        path_grants=[
            PathGrant(capability_id="file.read", path_prefix=str(root)),
            PathGrant(capability_id="text.search", path_prefix=str(root)),
        ],
    )


def _tool_call(mode: Mode, scenario: str, root: Path) -> ToolCall:
    capability_id, arguments = _tool_call_parts(scenario, root)
    return ToolCall(
        tool_call_id="wave3-{0}-{1}-tool-call".format(mode, scenario),
        capability_id=capability_id,
        arguments=arguments,
    )


def _tool_call_parts(scenario: str, root: Path) -> tuple[str, dict[str, str]]:
    fixture_path = str(root / "wave3.txt")
    scenarios = {
        "fake-read": ("file.read", {"path": fixture_path}),
        "fake-search": ("text.search", {"path": str(root), "query": "needle"}),
        "blocked-read": ("file.read", {"path": str(root.parent / "outside.txt")}),
        "unknown-tool": ("unknown.tool", {}),
    }
    return scenarios.get(scenario, ("unknown.tool", {}))


def _prompt_context(
    mode: Mode,
    scenario: str,
    user_text: str,
    visible_tools: list[str],
) -> dict[str, str | list[str]]:
    return {
        "mode": mode,
        "scenario": scenario,
        "request": "redacted:{0}".format(len(user_text)),
        "profile": PROFILE,
        "visible_tools": visible_tools,
    }


def _visible_tool_names(schema: list[dict[str, object]]) -> list[str]:
    names = []
    for entry in schema:
        function = entry.get("function")
        if isinstance(function, dict):
            name = function.get("name")
            if isinstance(name, str):
                names.append(name)
    return names
