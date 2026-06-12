from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, JsonValue

_DONE_MARKERS: tuple[str, ...] = (
    "done",
    "completed",
    "complete",
    "완료",
    "끝났",
    "finished",
)


class CompletionGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    completion_allowed: bool
    claimed_done: bool
    blocked_reasons: tuple[str, ...] = ()
    verified: tuple[str, ...] = ()
    claimed_artifacts: tuple[str, ...] = ()
    claimed_tests: tuple[str, ...] = ()
    executed_commands: tuple[str, ...] = ()

    def to_hook_output(self) -> dict[str, JsonValue]:
        action = "allow" if self.completion_allowed else "block"
        return {
            "action": action,
            "reason": "[Zeus] completion {0}".format(
                "verified" if self.completion_allowed else "unverified"
            ),
            "zeus": self.model_dump(mode="json"),
        }


def evaluate_completion_claim(
    payload: dict[str, JsonValue],
    *,
    artifact_root: Path | None = None,
) -> CompletionGateResult:
    final_message = _text(payload.get("final_message")) or _text(payload.get("message")) or ""
    claimed_artifacts = tuple(_string_list(payload.get("claimed_artifacts")))
    claimed_tests = tuple(_string_list(payload.get("claimed_tests")))
    executed_commands = tuple(_string_list(payload.get("executed_commands")))
    changed_paths = tuple(_string_list(payload.get("changed_paths")))
    claimed_done = _claims_done(final_message) or bool(claimed_artifacts or claimed_tests)
    blocked: list[str] = []
    verified: list[str] = []

    for artifact in claimed_artifacts:
        if _artifact_exists(artifact, artifact_root):
            verified.append("artifact_exists:{0}".format(artifact))
        else:
            blocked.append("missing_artifact:{0}".format(artifact))
    for command in claimed_tests:
        if _command_was_run(command, executed_commands):
            verified.append("test_command_ran:{0}".format(command))
        else:
            blocked.append("missing_test_command:{0}".format(command))
    if _mentions_file_change(final_message) and not claimed_artifacts and not changed_paths:
        blocked.append("missing_change_evidence")
    if claimed_done and not claimed_artifacts and not claimed_tests and not changed_paths:
        blocked.append("missing_completion_evidence")

    return CompletionGateResult(
        completion_allowed=not blocked,
        claimed_done=claimed_done,
        blocked_reasons=tuple(blocked),
        verified=tuple(verified),
        claimed_artifacts=claimed_artifacts,
        claimed_tests=claimed_tests,
        executed_commands=executed_commands,
    )


def _claims_done(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _DONE_MARKERS)


def _mentions_file_change(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in ("file", "파일", "wrote", "created", "수정", "생성"))


def _artifact_exists(value: str, artifact_root: Path | None) -> bool:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (artifact_root or Path.cwd()) / path
    return path.exists()


def _command_was_run(expected: str, executed: tuple[str, ...]) -> bool:
    normalized = expected.strip()
    return any(normalized == command.strip() for command in executed)


def _string_list(value: JsonValue | None) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _text(value: JsonValue | None) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
