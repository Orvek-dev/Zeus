from __future__ import annotations

import typer

from .approval_commands import register_approval_commands
from .core_commands import register_core_commands
from .dev_commands import register_dev_commands
from .evidence_commands import register_evidence_commands
from .mcp_commands import register_mcp_commands
from .ops_commands import register_ops_commands
from .policy_commands import register_policy_commands
from .proxy_commands import register_proxy_commands
from .tui_commands import register_tui_commands


def register_product_commands(app: typer.Typer) -> None:
    register_core_commands(app)
    register_approval_commands(app)
    register_tui_commands(app)
    register_evidence_commands(app)
    register_ops_commands(app)
    register_proxy_commands(app)
    register_policy_commands(app)
    register_mcp_commands(app)
    register_dev_commands(app)
