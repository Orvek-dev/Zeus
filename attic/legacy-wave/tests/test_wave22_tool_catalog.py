from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from zeus_agent.runtime_lease import RuntimeLease
from zeus_agent.tool_runtime import (
    ToolRuntimeRegistry,
    native_tool_catalog,
    native_tool_catalog_payload,
    register_native_tool_catalog,
)

_ISSUED_AT = datetime(2026, 6, 4, 0, 0, tzinfo=timezone.utc)
_EXPIRES_AT = datetime(2026, 6, 5, 0, 0, tzinfo=timezone.utc)


def test_native_tool_catalog_has_hermes_grade_shape() -> None:
    catalog = native_tool_catalog()
    tools = [tool for toolset in catalog for tool in toolset.tools]
    names = [tool.name for tool in tools]
    capability_ids = [tool.capability_id for tool in tools]
    payload = native_tool_catalog_payload()

    assert len(catalog) == 25
    assert len(tools) == 80
    assert len(names) == len(set(names))
    assert len(capability_ids) == len(set(capability_ids))
    assert all(tool.source == "local" for tool in tools)
    assert all(capability_id.startswith("api.tool.") for capability_id in capability_ids)
    assert payload["toolset_count"] == 25
    assert payload["tool_count"] == 80
    assert payload["live_production_claimed"] is False
    assert "raw_secret" not in json.dumps(payload)


def test_native_tool_catalog_compiles_only_lease_visible_tools() -> None:
    catalog = native_tool_catalog()
    first_toolset = catalog[0]
    allowed = tuple(tool.capability_id for tool in first_toolset.tools)
    runtime = ToolRuntimeRegistry()
    register_native_tool_catalog(runtime)
    lease = RuntimeLease(
        lease_id="wave22.lease.tool_catalog",
        objective_id="wave22.objective.tool_catalog",
        principal_id="wave22.principal.local",
        run_id="wave22.run.tool_catalog",
        allowed_capabilities=allowed,
        budget_limit=100,
        evidence_target="mneme.wave22.tool_catalog",
        issued_at=_ISSUED_AT,
        expires_at=_EXPIRES_AT,
    )

    schema = runtime.compile_model_schema(lease, now=_ISSUED_AT)

    visible_names = {entry["function"]["name"] for entry in schema}
    assert visible_names == {tool.name for tool in first_toolset.tools}
    assert len(visible_names) == len(first_toolset.tools)
    assert "ignore previous" not in json.dumps(schema).lower()


def test_tool_catalog_cli_returns_parsed_catalog_payload() -> None:
    env = {**os.environ, "PYTHONPATH": "src"}

    proc = subprocess.run(
        [sys.executable, "-m", "zeus_agent", "tool-catalog", "--json"],
        cwd=".",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["toolset_count"] == 25
    assert payload["tool_count"] == 80
    assert payload["live_production_claimed"] is False
