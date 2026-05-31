"""Run-oriented storage for blueprint and approval artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from zeus_agent.paths import ensure_private_dir, init_home, runs_dir
from zeus_agent.schemas.approval import ApprovalRecord
from zeus_agent.schemas.execution_spec import ExecutionSpec
from zeus_agent.schemas.goal_contract import GoalContract
from zeus_agent.storage.jsonio import append_private_jsonl, read_json, write_private_json


@dataclass(frozen=True)
class RunArtifacts:
    run_id: str
    run_dir: Path
    goal_contract_path: Path
    execution_spec_path: Path
    approvals_path: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "goal_contract_path": str(self.goal_contract_path),
            "execution_spec_path": str(self.execution_spec_path),
            "approvals_path": str(self.approvals_path),
        }


class RunStore:
    def __init__(self, home: Path | None = None) -> None:
        paths = init_home(home)
        self.home = paths["home"]
        self.root = runs_dir(self.home)

    def artifacts_for(self, run_id: str) -> RunArtifacts:
        run_dir = self.root / run_id
        return RunArtifacts(
            run_id=run_id,
            run_dir=run_dir,
            goal_contract_path=run_dir / "goal_contract.json",
            execution_spec_path=run_dir / "execution_spec.json",
            approvals_path=run_dir / "approvals.jsonl",
        )

    def save_blueprint(
        self,
        goal_contract: GoalContract,
        execution_spec: ExecutionSpec,
    ) -> RunArtifacts:
        artifacts = self.artifacts_for(execution_spec.run_id)
        ensure_private_dir(artifacts.run_dir)
        write_private_json(
            artifacts.goal_contract_path,
            goal_contract.model_dump(mode="json"),
        )
        write_private_json(
            artifacts.execution_spec_path,
            execution_spec.model_dump(mode="json"),
        )
        return artifacts

    def load_goal_contract(self, run_id: str) -> GoalContract:
        return GoalContract.model_validate(read_json(self.artifacts_for(run_id).goal_contract_path))

    def load_execution_spec(self, run_id: str) -> ExecutionSpec:
        return ExecutionSpec.model_validate(read_json(self.artifacts_for(run_id).execution_spec_path))

    def update_goal_contract(self, goal_contract: GoalContract, run_id: str) -> Path:
        return write_private_json(
            self.artifacts_for(run_id).goal_contract_path,
            goal_contract.model_dump(mode="json"),
        )

    def update_execution_spec(self, execution_spec: ExecutionSpec) -> Path:
        return write_private_json(
            self.artifacts_for(execution_spec.run_id).execution_spec_path,
            execution_spec.model_dump(mode="json"),
        )

    def append_approval(self, record: ApprovalRecord) -> Path:
        return append_private_jsonl(
            self.artifacts_for(record.run_id).approvals_path,
            record.model_dump(mode="json"),
        )

    def list_runs(self, limit: int = 50) -> list[dict[str, str]]:
        if not self.root.exists():
            return []
        run_dirs = sorted(
            (path for path in self.root.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        results: list[dict[str, str]] = []
        for run_dir in run_dirs[:limit]:
            artifacts = self.artifacts_for(run_dir.name)
            status = "missing"
            goal = ""
            created_at = ""
            if artifacts.goal_contract_path.exists():
                contract = self.load_goal_contract(run_dir.name)
                status = contract.approval_state
                goal = contract.normalized_goal
                created_at = contract.created_at.isoformat()
            results.append(
                {
                    "run_id": run_dir.name,
                    "status": status,
                    "created_at": created_at,
                    "goal": goal,
                    "run_dir": str(run_dir),
                }
            )
        return results
