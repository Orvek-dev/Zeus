"""Local filesystem layout for Zeus.

Zeus state is local-first and private by default. The default home is
``~/.zeus`` and can be overridden with ``ZEUS_HOME`` for tests or isolated
workspaces.
"""

from __future__ import annotations

import os
from pathlib import Path

ZEUS_HOME_ENV = "ZEUS_HOME"

PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


def zeus_home() -> Path:
    configured = os.environ.get(ZEUS_HOME_ENV)
    return Path(configured or "~/.zeus").expanduser().resolve()


def ensure_private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, PRIVATE_DIR_MODE)
    except PermissionError:
        pass
    return path


def ensure_private_file(path: Path) -> Path:
    ensure_private_dir(path.parent)
    path.touch(exist_ok=True)
    try:
        os.chmod(path, PRIVATE_FILE_MODE)
    except PermissionError:
        pass
    return path


def data_dir(home: Path | None = None) -> Path:
    return (home or zeus_home()) / "data"


def runs_dir(home: Path | None = None) -> Path:
    return data_dir(home) / "runs"


def events_dir(home: Path | None = None) -> Path:
    return data_dir(home) / "events"


def config_dir(home: Path | None = None) -> Path:
    return (home or zeus_home()) / "config"


def skills_dir(home: Path | None = None) -> Path:
    return (home or zeus_home()) / "skills"


def artifacts_dir(home: Path | None = None) -> Path:
    return (home or zeus_home()) / "artifacts"


def logs_dir(home: Path | None = None) -> Path:
    return (home or zeus_home()) / "logs"


def sandboxes_dir(home: Path | None = None) -> Path:
    return data_dir(home) / "sandboxes"


def registry_dir(home: Path | None = None) -> Path:
    return data_dir(home) / "registry"


def checkpoints_dir(home: Path | None = None) -> Path:
    return data_dir(home) / "checkpoints"


def state_db_path(home: Path | None = None) -> Path:
    return data_dir(home) / "state.db"


def init_home(home: Path | None = None) -> dict[str, Path]:
    root = ensure_private_dir(home or zeus_home())
    paths = {
        "home": root,
        "data": ensure_private_dir(data_dir(root)),
        "runs": ensure_private_dir(runs_dir(root)),
        "events": ensure_private_dir(events_dir(root)),
        "config": ensure_private_dir(config_dir(root)),
        "skills": ensure_private_dir(skills_dir(root)),
        "artifacts": ensure_private_dir(artifacts_dir(root)),
        "logs": ensure_private_dir(logs_dir(root)),
        "sandboxes": ensure_private_dir(sandboxes_dir(root)),
        "registry": ensure_private_dir(registry_dir(root)),
        "checkpoints": ensure_private_dir(checkpoints_dir(root)),
    }
    marker = root / ".gitignore"
    if not marker.exists():
        marker.write_text("*\n", encoding="utf-8")
        try:
            os.chmod(marker, PRIVATE_FILE_MODE)
        except PermissionError:
            pass
    return paths
