from __future__ import annotations

import typer

from zeus_agent.cli_wave162 import register_wave162_commands
from zeus_agent.cli_wave175 import register_wave175_commands
from zeus_agent.cli_wave177 import register_wave177_commands
from zeus_agent.cli_wave179 import register_wave179_commands
from zeus_agent.cli_wave180 import register_wave180_commands
from zeus_agent.cli_wave183 import register_wave183_commands
from zeus_agent.cli_wave185 import register_wave185_commands
from zeus_agent.cli_wave189 import register_wave189_commands
from zeus_agent.cli_wave190 import register_wave190_commands
from zeus_agent.cli_wave191 import register_wave191_commands


def register_live_research_workflow_commands(app: typer.Typer) -> None:
    register_wave162_commands(app)
    register_wave175_commands(app)
    register_wave177_commands(app)
    register_wave179_commands(app)
    register_wave180_commands(app)
    register_wave183_commands(app)
    register_wave185_commands(app)
    register_wave189_commands(app)
    register_wave190_commands(app)
    register_wave191_commands(app)
