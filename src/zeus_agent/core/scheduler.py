"""Cron-style local schedule registry.

This module records schedule intent only. It does not install system crontabs
or launch background daemons without a separate user-approved runner.
"""

from __future__ import annotations

from pathlib import Path

from zeus_agent.paths import registry_dir, ensure_private_dir
from zeus_agent.schemas.plugin import CronJobSpec
from zeus_agent.schemas.trace_event import new_trace_event
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.jsonio import read_json, write_private_json


def add_cron_job(
    name: str,
    schedule: str,
    command: list[str],
    *,
    enabled: bool = False,
    home: Path | None = None,
) -> CronJobSpec:
    spec = CronJobSpec(
        name=name,
        schedule=schedule,
        command=command,
        enabled=False if enabled else False,
        requires_approval=True,
    )
    jobs = list_cron_jobs(home=home)
    jobs.append(spec)
    _write_jobs(jobs, home=home)
    EventLog(home).append(
        new_trace_event("scheduler.cron_job.added", payload={"job_id": spec.job_id, "name": name, "enabled": spec.enabled})
    )
    return spec


def list_cron_jobs(*, home: Path | None = None) -> list[CronJobSpec]:
    path = _jobs_path(home)
    if not path.exists():
        return []
    return [CronJobSpec.model_validate(item) for item in read_json(path)]


def _write_jobs(jobs: list[CronJobSpec], *, home: Path | None = None) -> Path:
    return write_private_json(_jobs_path(home), [job.model_dump(mode="json") for job in jobs])


def _jobs_path(home: Path | None = None) -> Path:
    path = registry_dir(home) / "cron_jobs.json"
    ensure_private_dir(path.parent)
    return path

