import os

from zeus_agent.core.approvals import approve_run, reject_run
from zeus_agent.core.blueprint import build_blueprint
from zeus_agent.schemas.trace_event import new_trace_event
from zeus_agent.storage.event_log import EventLog
from zeus_agent.storage.run_store import RunStore


def test_run_store_persists_private_blueprint_files(tmp_path):
    home = tmp_path / "zeus-home"
    bundle = build_blueprint("Create a local report", workspace=tmp_path)

    artifacts = RunStore(home).save_blueprint(bundle.goal_contract, bundle.execution_spec)

    assert artifacts.goal_contract_path.exists()
    assert artifacts.execution_spec_path.exists()
    assert oct(os.stat(artifacts.goal_contract_path).st_mode & 0o777) == "0o600"
    assert oct(os.stat(artifacts.execution_spec_path).st_mode & 0o777) == "0o600"


def test_approval_and_rejection_update_state(tmp_path):
    home = tmp_path / "zeus-home"
    bundle = build_blueprint("Create a local report", workspace=tmp_path)
    run_id = bundle.execution_spec.run_id
    store = RunStore(home)
    store.save_blueprint(bundle.goal_contract, bundle.execution_spec)

    approval, status = approve_run(run_id, approval_text="looks good", home=home)

    assert approval.decision == "approved"
    assert status["approval_state"] == "approved"
    assert status["execution_mode"] == "sandbox_after_approval"
    assert store.load_goal_contract(run_id).approval_state == "approved"
    assert store.load_execution_spec(run_id).status == "approved"

    rejection, rejected_status = reject_run(run_id, reason="scope changed", home=home)

    assert rejection.decision == "rejected"
    assert rejected_status["approval_state"] == "rejected"
    assert store.load_execution_spec(run_id).status == "rejected"


def test_event_log_redacts_payload(tmp_path):
    home = tmp_path / "zeus-home"
    event = new_trace_event(
        "test.redaction",
        payload={"note": "token=verysecretvalue"},
    )
    log = EventLog(home)
    log.append(event)

    events = log.read_all()

    assert events[0]["redaction_status"] == "redacted"
    assert "verysecretvalue" not in str(events[0])
