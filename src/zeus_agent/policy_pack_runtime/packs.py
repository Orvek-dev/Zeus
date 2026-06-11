from __future__ import annotations

from typing import Final, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from zeus_agent.capability_registry_runtime import (
    CapabilityRecord,
    CapabilityStatus,
    CapabilityTrust,
    CostModel,
    Provenance,
    SideEffectClass,
    VerbClass,
)
from zeus_agent.decision_api_runtime import ZeusDecisionEngine
from zeus_agent.trust_loop_runtime import Reversibility, SQLiteControlPlaneStore

_MICROUSD_PER_USD: Final = 1_000_000


class PolicyPack(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    name: str
    description: str
    weekly_budget_usd: float = Field(gt=0)
    rate_max_calls: int = Field(default=30, gt=0)
    rate_window_seconds: int = Field(default=60, gt=0)
    quiet_hours: Optional[str] = None  # "22-07" local
    never_do: tuple[str, ...] = ()  # capability ids locked outright


BUILTIN_PACKS: Final[tuple[PolicyPack, ...]] = (
    PolicyPack(
        name="safe-assistant",
        description="일상 비서: 읽기는 자유, 바깥으로 나가는 모든 것은 묻는다",
        weekly_budget_usd=5.0,
        rate_max_calls=20,
        quiet_hours="22-07",
        never_do=("payments.transfer", "fs.delete_recursive", "account.delete"),
    ),
    PolicyPack(
        name="coding",
        description="개발 작업: 로컬 변경 관대, 외부 발신·푸시는 승인",
        weekly_budget_usd=25.0,
        rate_max_calls=60,
        never_do=("payments.transfer", "account.delete"),
    ),
    PolicyPack(
        name="sns-ops",
        description="SNS 운영: 발행 행동 중심이므로 모든 공개 쓰기는 기록·제한",
        weekly_budget_usd=10.0,
        rate_max_calls=15,
        quiet_hours="23-06",
        never_do=("payments.transfer", "account.delete", "fs.delete_recursive"),
    ),
)


def pack_by_name(name: str) -> Optional[PolicyPack]:
    for pack in BUILTIN_PACKS:
        if pack.name == name.strip():
            return pack
    return None


def onboarding_pack(
    *, task: str, monthly_cap_usd: float, never_do: tuple[str, ...]
) -> PolicyPack:
    """The 3-question onboarding → a personal pack (no LLM, pure derivation)."""
    base = pack_by_name("coding") if "cod" in task.lower() or "개발" in task else pack_by_name("safe-assistant")
    assert base is not None
    return base.model_copy(
        update={
            "name": "personal",
            "description": "온보딩 답변으로 생성된 개인 정책 ({0})".format(task.strip() or "general"),
            "weekly_budget_usd": max(monthly_cap_usd / 4.0, 0.01),
            "never_do": tuple(dict.fromkeys(base.never_do + never_do)),
        }
    )


def apply_pack(
    pack: PolicyPack,
    *,
    engine: ZeusDecisionEngine,
    store: SQLiteControlPlaneStore,
    confirmed: bool,
    principal_id: str = "operator.local",
) -> dict[str, JsonValue]:
    """Apply a pack — governed. Unconfirmed → nothing changes, the request
    parks as evidence. Confirmed (the human at the console IS the approval)
    → rules land in the shared store and every gate inherits them."""
    if not confirmed:
        event = engine.recorder.record_decision(
            run_id="run.policy.change",
            payload={
                "capability_id": "policy.change",
                "decision": "ask",
                "reason": "operator_confirmation_required",
                "pack": pack.name,
                "principal_id": principal_id,
            },
        )
        return {
            "applied": False,
            "reason": "confirm required: rerun with --confirm",
            "receipt_id": event.record_id,
        }

    week_units = int(pack.weekly_budget_usd * _MICROUSD_PER_USD)
    store.set_budget_limit("fleet", "fleet", week_units)
    store.kv_set("governor.rate_max_calls", str(pack.rate_max_calls))
    store.kv_set("governor.rate_window_seconds", str(pack.rate_window_seconds))
    if pack.quiet_hours:
        store.kv_set("policy.quiet_hours", pack.quiet_hours)
    store.kv_set("policy.active_pack", pack.name)
    for capability_id in pack.never_do:
        record = _lock_record(capability_id)
        store.capability_save(capability_id, record.model_dump_json())
        engine.capabilities.register(record)
    event = engine.recorder.record_decision(
        run_id="run.policy.change",
        payload={
            "capability_id": "policy.change",
            "decision": "allow",
            "reason": "operator_confirmed",
            "pack": pack.name,
            "weekly_budget_units": week_units,
            "never_do": list(pack.never_do),
            "quiet_hours": pack.quiet_hours,
            "principal_id": principal_id,
        },
    )
    return {
        "applied": True,
        "pack": pack.name,
        "weekly_budget_units": week_units,
        "never_do": list(pack.never_do),
        "receipt_id": event.record_id,
    }


def _lock_record(capability_id: str) -> CapabilityRecord:
    """never-do = a quarantined record every gate loads: decide() DENYs it."""
    return CapabilityRecord(
        capability_id=capability_id,
        verb_class=VerbClass.transform,
        title="locked by policy pack",
        input_summary="locked",
        output_summary="locked",
        side_effect=SideEffectClass.account_write,
        reversibility=Reversibility.irreversible,
        cost_model=CostModel(),
        trust=CapabilityTrust(score=0.0, runs=0, success_rate=0.0, measured=False),
        provenance=Provenance.builtin,
        status=CapabilityStatus.quarantined,
    )
