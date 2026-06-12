from __future__ import annotations

from pydantic import JsonValue

from zeus_agent.trust_loop_runtime import ActionRisk, ParkedAction, Reversibility


def short_parked_id(parked_action_id: str) -> str:
    parts = [part for part in parked_action_id.split(".") if part]
    return ".".join(parts[-2:]) if len(parts) >= 2 else parked_action_id[-12:]


def pending_card(parked: ParkedAction) -> dict[str, JsonValue]:
    action = parked.action
    hard_risk = action.risk is ActionRisk.high or action.reversibility is Reversibility.irreversible
    approval_effect = "exact_payload_replay_once" if hard_risk else "once_grant"
    return {
        "short_id": short_parked_id(parked.parked_action_id),
        "parked_action_id": parked.parked_action_id,
        "capability_id": action.capability_id,
        "host": parked.host,
        "session_id": parked.session_id,
        "risk": action.risk.value,
        "reversibility": action.reversibility.value,
        "payload": action.payload,
        "card": {
            "title": "Approval required",
            "what": action.capability_id,
            "why": "operator approval required before release",
            "approval_effect": approval_effect,
            "actions": ("confirm", "approve_once", "deny", "narrow", "freeze"),
        },
        "created_at": parked.created_at.isoformat(),
        "expires_at": parked.expires_at.isoformat(),
        "operator_note": (
            "resolve in Zeus control tower or a separate operator terminal; "
            "do not paste Zeus commands into the governed host"
        ),
    }
