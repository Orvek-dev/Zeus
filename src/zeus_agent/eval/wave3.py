from __future__ import annotations

import json
import tempfile
from pathlib import Path

from zeus_agent.agent_runtime.surfaces import chat_wave3_surface, run_wave3_surface
from zeus_agent.capability_runtime import build_wave3_capability_graph, build_wave3_handlers
from zeus_agent.kernel.authority import AuthorityContext, CapabilityGrant, PathGrant
from zeus_agent.kernel.broker import CapabilityBroker
from zeus_agent.model_runtime.providers import ProviderRouteRequest, default_provider_router

WAVE3_ADAPTER_REQ = "REQ-ZEUS-WAVE3-006:S1"
PROFILE = "coding-agent"


def run_wave3_eval() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="zeus-wave3-eval-") as temp_home:
        home = Path(temp_home)
        checks = [
            _check("broker", _broker_passes(home)),
            _check("adapter", _adapter_passes(home)),
            _check("provider", _provider_passes()),
            _check("runtime", _runtime_passes(home)),
            _check("cli_smoke", _cli_smoke_passes(home)),
        ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    total = len(checks)
    return {
        "suite": "wave3",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "checks": checks,
    }


def _check(name: str, passed: bool) -> dict[str, str]:
    return {"name": name, "status": "pass" if passed else "fail"}


def _broker_passes(home: Path) -> bool:
    root = _fixture_root(home / "broker")
    broker = CapabilityBroker(
        graph=build_wave3_capability_graph(),
        handlers=build_wave3_handlers(root),
    )
    response = broker.dispatch(
        capability_id="file.read",
        payload={"path": str(root / "wave3.txt")},
        context=_authority(root),
        profile=PROFILE,
        criterion_id=WAVE3_ADAPTER_REQ,
    )
    return response["decision"] == "allowed" and response["evidence"]["status"] == "pass"


def _adapter_passes(home: Path) -> bool:
    root = _fixture_root(home / "adapter")
    handler = build_wave3_handlers(root)["text.search"]
    result = handler({"path": str(root), "query": "needle"})
    return isinstance(result, dict) and result.get("matches") == [
        {"path": "wave3.txt", "line": 2, "snippet": "needle: wave3 searchable line"}
    ]


def _provider_passes() -> bool:
    route = default_provider_router().route(
        ProviderRouteRequest(
            provider="fake",
            required_tool_calling=True,
            required_json_mode=True,
            local_private=True,
            network_allowed=False,
        )
    )
    return route.decision == "selected" and route.provider_id == "fake-local"


def _runtime_passes(home: Path) -> bool:
    payload = run_wave3_surface("eval runtime", home / "runtime")
    completion = payload["completion"]
    return isinstance(completion, dict) and completion.get("status") == "complete"


def _cli_smoke_passes(home: Path) -> bool:
    payload = chat_wave3_surface("eval cli smoke", home / "cli")
    encoded = json.dumps(payload, sort_keys=True)
    broker = payload["broker_decision"]
    return (
        "eval cli smoke" not in encoded
        and isinstance(broker, dict)
        and broker.get("decision") == "allowed"
    )


def _fixture_root(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "wave3.txt").write_text(
        "wave3 fixture content\nneedle: wave3 searchable line\n",
        encoding="utf-8",
    )
    return root.resolve()


def _authority(root: Path) -> AuthorityContext:
    return AuthorityContext(
        principal_id="wave3-eval-principal",
        run_id="wave3-eval-run",
        goal_contract_id="wave3-eval-goal",
        capability_grants=[
            CapabilityGrant(capability_id="file.read"),
            CapabilityGrant(capability_id="text.search"),
        ],
        path_grants=[
            PathGrant(capability_id="file.read", path_prefix=str(root)),
            PathGrant(capability_id="text.search", path_prefix=str(root)),
        ],
    )
