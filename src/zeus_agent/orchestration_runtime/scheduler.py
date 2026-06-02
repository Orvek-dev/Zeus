from __future__ import annotations

from typing import Sequence

from .models import (
    ParallelSchedule,
    ParallelTaskSpec,
    ParallelWavePlan,
)


class ParallelScheduler:
    def plan(self, tasks: Sequence[ParallelTaskSpec]) -> ParallelSchedule:
        specs = list(tasks)
        sorted_specs = sorted(specs, key=lambda item: item.task_id)
        task_map: dict[str, ParallelTaskSpec] = {}
        duplicates: list[str] = []
        for spec in sorted_specs:
            if spec.task_id in task_map:
                duplicates.append(spec.task_id)
            task_map[spec.task_id] = spec

        blocked_reasons: list[str] = []
        blocked_reasons.extend(self._validate_task_basics(task_map, duplicates))
        if blocked_reasons:
            return self._blocked_schedule(blocked_reasons)

        blocked_reasons.extend(self._detect_dependency_cycle(task_map))
        blocked_reasons.extend(self._validate_owned_path_conflicts(task_map))

        if blocked_reasons:
            return self._blocked_schedule(blocked_reasons)

        waves = self._build_waves(task_map)
        return ParallelSchedule(
            decision="planned",
            reason="parallel_schedule_planned",
            waves=tuple(waves),
            blocked_reasons=(),
            handler_executed=False,
            network_opened=False,
        )

    def _blocked_schedule(self, blocked_reasons: list[str]) -> ParallelSchedule:
        return ParallelSchedule(
            decision="blocked",
            reason="parallel_schedule_blocked",
            waves=(),
            blocked_reasons=tuple(blocked_reasons),
            handler_executed=False,
            network_opened=False,
        )

    def _validate_task_basics(
        self,
        task_map: dict[str, ParallelTaskSpec],
        duplicate_task_ids: list[str],
    ) -> list[str]:
        reasons: list[str] = []
        for task_id in sorted(set(duplicate_task_ids)):
            reasons.append("task_id:{0}:duplicate".format(task_id))

        for task_id in sorted(task_map):
            task = task_map[task_id]
            if task.evidence_target is None:
                reasons.append("evidence_target:{0}:missing".format(task_id))
            if task.subagent_depth > 1:
                reasons.append("subagent_depth:{0}:exceeds_one".format(task_id))
            if task.live_capable and "allow_live_network" not in task.security_decisions:
                reasons.append("security:{0}:missing_live_allow".format(task_id))

        for task in task_map.values():
            for dependency_id in task.depends_on:
                if dependency_id not in task_map:
                    reasons.append(
                        "depends_on:{0}:missing:{1}".format(task.task_id, dependency_id),
                    )

        return sorted(set(reasons))

    def _detect_dependency_cycle(self, task_map: dict[str, ParallelTaskSpec]) -> list[str]:
        state: dict[str, int] = {task_id: 0 for task_id in task_map}
        path: list[str] = []
        position: dict[str, int] = {}
        for task_id in sorted(task_map):
            if state[task_id] == 0:
                cycle = self._dfs(task_id, task_map, state, path, position)
                if cycle is not None:
                    return [cycle]
        return []

    def _dfs(
        self,
        task_id: str,
        task_map: dict[str, ParallelTaskSpec],
        state: dict[str, int],
        path: list[str],
        position: dict[str, int],
    ) -> str | None:
        state[task_id] = 1
        position[task_id] = len(path)
        path.append(task_id)
        for dependency in task_map[task_id].depends_on:
            if dependency not in task_map:
                continue
            if state[dependency] == 0:
                cycle = self._dfs(dependency, task_map, state, path, position)
                if cycle is not None:
                    return cycle
            if state[dependency] == 1:
                start = position[dependency]
                cycle = path[start:]
                if cycle[-1] == dependency:
                    cycle.pop()
                if len(cycle) == 2:
                    return "cycle:{0}<->{1}".format(cycle[0], cycle[1])
                return "cycle:{0}".format("<->".join(cycle))
        path.pop()
        state[task_id] = 2
        position.pop(task_id, None)
        return None

    def _validate_owned_path_conflicts(self, task_map: dict[str, ParallelTaskSpec]) -> list[str]:
        task_ids = sorted(task_map)
        reasons: list[str] = []
        for left_index, left_id in enumerate(task_ids):
            left_paths = task_map[left_id].owned_paths
            for right_id in task_ids[left_index + 1 :]:
                right_paths = task_map[right_id].owned_paths
                if self._depends_on_path(task_map, left_id, right_id):
                    continue
                if self._depends_on_path(task_map, right_id, left_id):
                    continue
                if self._paths_overlap(left_paths, right_paths):
                    reasons.append("owned_path_conflict:{0}:{1}".format(left_id, right_id))
        return reasons

    def _build_waves(self, task_map: dict[str, ParallelTaskSpec]) -> list[ParallelWavePlan]:
        in_degree = {task_id: 0 for task_id in task_map}
        dependents: dict[str, list[str]] = {task_id: [] for task_id in task_map}

        for task in task_map.values():
            for dependency_id in task.depends_on:
                in_degree[task.task_id] += 1
                dependents[dependency_id].append(task.task_id)

        available = sorted([task_id for task_id, count in in_degree.items() if count == 0])
        blocked: set[str] = set()
        waves: list[ParallelWavePlan] = []
        scheduled: set[str] = set()
        wave_index = 0

        while len(scheduled) < len(task_map):
            if not available:
                return waves
            scheduled_now: list[str] = []
            claim_set: list[str] = []

            for candidate in available:
                if candidate in blocked:
                    continue
                if self._paths_overlap(task_map[candidate].owned_paths, tuple(claim_set)):
                    continue
                scheduled_now.append(candidate)
                claim_set.extend(task_map[candidate].owned_paths)
                blocked.add(candidate)

            if not scheduled_now:
                forced = available[0]
                scheduled_now.append(forced)
                claim_set.extend(task_map[forced].owned_paths)
                blocked.add(forced)

            for task_id in scheduled_now:
                scheduled.add(task_id)
                if task_id in available:
                    available.remove(task_id)

            next_available: list[str] = []
            for task_id in scheduled_now:
                for dependent_id in dependents[task_id]:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        next_available.append(dependent_id)
            if next_available:
                next_available.sort()
            blocked = {value for value in blocked if value in scheduled}
            available = sorted(set(available).union(next_available))
            wave = ParallelWavePlan(
                wave_index=wave_index,
                task_ids=tuple(scheduled_now),
                manual_qa_channels=tuple(
                    sorted({task_map[task_id].manual_qa_channel for task_id in scheduled_now})
                ),
            )
            waves.append(wave)
            wave_index += 1

        return waves

    def _depends_on_path(
        self,
        task_map: dict[str, ParallelTaskSpec],
        source_id: str,
        target_id: str,
    ) -> bool:
        if source_id == target_id:
            return False
        seen: set[str] = set()
        stack: list[str] = [source_id]
        while stack:
            current = stack.pop()
            if current == target_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(task_map[current].depends_on)
        return False

    def _paths_overlap(
        self,
        left_paths: tuple[str, ...],
        right_paths: tuple[str, ...],
    ) -> bool:
        normalized_left = [_normalize_path(path) for path in left_paths]
        normalized_right = [_normalize_path(path) for path in right_paths]
        for left in normalized_left:
            for right in normalized_right:
                if left == right:
                    return True
                if left.startswith(right + "/"):
                    return True
                if right.startswith(left + "/"):
                    return True
        return False

def _normalize_path(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized.endswith("/**"):
        normalized = normalized[:-3]
    return normalized
