from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.gateway_pairing_runtime.models import GatewayPairingListResult, GatewayPairingProofResult
from zeus_agent.security.credentials import redact_secret_spans

_UNSAFE_REF_MARKERS: Final[tuple[str, ...]] = (
    "ignore previous",
    "ignore system",
    "override system",
    "reveal prompt",
    "jailbreak",
)
_SECRET_MARKERS: Final[tuple[str, ...]] = (
    "sk-wave",
    "ghp_",
    "github_pat_",
    "glpat-",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "bearer ",
    "token=sk",
    "password=",
    "secret=",
    "private_key",
    "private-key",
    "-----begin",
)


class GatewayPairingRuntime:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.config_path = home / "gateway-pairings.json"
        self.gateway_config_path = home / "gateway-config.json"

    def pair(self, *, adapter_id: str, target: str, proof_ref: str) -> GatewayPairingProofResult:
        clean_adapter_id = adapter_id.strip()
        clean_target = target.strip()
        clean_proof_ref = proof_ref.strip()
        blocked_reasons, redacted_input = self._blockers(
            adapter_id=clean_adapter_id,
            target=clean_target,
            proof_ref=clean_proof_ref,
        )
        if blocked_reasons:
            return _proof_result(
                decision="blocked",
                pairing=None,
                blocked_reasons=blocked_reasons,
                redacted_input=redacted_input,
            )

        pairing = {
            "adapter_id": clean_adapter_id,
            "target": clean_target,
            "proof_ref": clean_proof_ref,
            "pairing_configured": True,
            "proof_material_accessed": False,
            "credential_material_accessed": False,
            "network_opened": False,
            "handler_executed": False,
            "external_delivery_opened": False,
            "live_production_claimed": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        pairings = [
            item
            for item in self._pairings()
            if item["adapter_id"] != clean_adapter_id or item["target"] != clean_target
        ]
        pairings.append(pairing)
        self.home.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps({"pairings": pairings}, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return _proof_result(
            decision="paired",
            pairing=pairing,
            blocked_reasons=(),
            redacted_input=None,
        )

    def list(self) -> GatewayPairingListResult:
        result = GatewayPairingListResult(
            decision="report",
            paired_target_count=len(self._pairings()),
            pairings=self._pairings(),
            config_path=str(self.config_path),
            proof_material_accessed=False,
            credential_material_accessed=False,
            network_opened=False,
            handler_executed=False,
            external_delivery_opened=False,
            live_production_claimed=False,
        )
        return result.model_copy(update={"no_secret_echo": _no_secret_echo(result.to_payload())})

    def is_paired(self, *, adapter_id: str, target: str) -> bool:
        return any(
            item["adapter_id"] == adapter_id and item["target"] == target
            for item in self._pairings()
        )

    def _blockers(self, *, adapter_id: str, target: str, proof_ref: str) -> tuple[tuple[str, ...], Optional[str]]:
        reasons = []
        redacted_values = []
        if adapter_id == "":
            reasons.append("empty_gateway_adapter")
        if target == "":
            reasons.append("empty_gateway_target")
        if proof_ref == "":
            reasons.append("empty_pairing_proof_ref")
        safe_adapter_id = redact_secret_spans(adapter_id)
        safe_target = redact_secret_spans(target)
        safe_proof_ref = redact_secret_spans(proof_ref)
        if safe_adapter_id != adapter_id or _unsafe_ref(adapter_id):
            reasons.append("unsafe_gateway_adapter")
            redacted_values.append(safe_adapter_id)
        if safe_target != target or _unsafe_ref(target):
            reasons.append("unsafe_gateway_target")
            redacted_values.append(safe_target)
        if safe_proof_ref != proof_ref or _unsafe_ref(proof_ref):
            reasons.append("unsafe_pairing_proof_ref")
            redacted_values.append(safe_proof_ref)
        if not self._configured_target_exists(adapter_id=adapter_id, target=target):
            reasons.append("unknown_gateway_target")
        return tuple(dict.fromkeys(reasons)), _join_redacted(redacted_values)

    def _configured_target_exists(self, *, adapter_id: str, target: str) -> bool:
        return any(
            item.get("adapter_id") == adapter_id and item.get("target") == target
            for item in self._configured_targets()
        )

    def _configured_targets(self) -> tuple[dict[str, JsonValue], ...]:
        if not self.gateway_config_path.exists():
            return ()
        try:
            payload = json.loads(self.gateway_config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ()
        if not isinstance(payload, dict):
            return ()
        raw_targets = payload.get("targets", [])
        if not isinstance(raw_targets, list):
            return ()
        return tuple(
            {
                "adapter_id": str(item["adapter_id"]),
                "target": str(item["target"]),
            }
            for item in raw_targets
            if isinstance(item, dict)
            and isinstance(item.get("adapter_id"), str)
            and isinstance(item.get("target"), str)
        )

    def _pairings(self) -> tuple[dict[str, JsonValue], ...]:
        if not self.config_path.exists():
            return ()
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ()
        if not isinstance(payload, dict):
            return ()
        raw_pairings = payload.get("pairings", [])
        if not isinstance(raw_pairings, list):
            return ()
        pairings = []
        for item in raw_pairings:
            normalized = _normalize_pairing(item)
            if normalized is not None and self._configured_target_exists(
                adapter_id=str(normalized["adapter_id"]),
                target=str(normalized["target"]),
            ):
                pairings.append(normalized)
        return tuple(pairings)


def _normalize_pairing(item: object) -> Optional[dict[str, JsonValue]]:
    if not isinstance(item, dict):
        return None
    if not isinstance(item.get("adapter_id"), str) or not isinstance(item.get("target"), str):
        return None
    if not isinstance(item.get("proof_ref"), str):
        return None
    adapter_id = redact_secret_spans(str(item["adapter_id"]))
    target = redact_secret_spans(str(item["target"]))
    proof_ref = redact_secret_spans(str(item["proof_ref"]))
    if adapter_id != item["adapter_id"] or target != item["target"] or proof_ref != item["proof_ref"]:
        return None
    return {
        "adapter_id": adapter_id,
        "target": target,
        "proof_ref": proof_ref,
        "pairing_configured": True,
        "proof_material_accessed": False,
        "credential_material_accessed": False,
        "network_opened": False,
        "handler_executed": False,
        "external_delivery_opened": False,
        "live_production_claimed": False,
        "updated_at": str(item.get("updated_at", "")),
    }


def _proof_result(
    *,
    decision: str,
    pairing: Optional[dict[str, JsonValue]],
    blocked_reasons: tuple[str, ...],
    redacted_input: Optional[str],
) -> GatewayPairingProofResult:
    result = GatewayPairingProofResult(
        decision=decision,
        pairing=pairing,
        blocked_reasons=blocked_reasons,
        redacted_input=redacted_input,
        pairing_configured=pairing is not None,
        proof_material_accessed=False,
        credential_material_accessed=False,
        network_opened=False,
        handler_executed=False,
        external_delivery_opened=False,
        live_production_claimed=False,
    )
    return result.model_copy(update={"no_secret_echo": _no_secret_echo(result.to_payload())})


def _unsafe_ref(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in _UNSAFE_REF_MARKERS)


def _join_redacted(values: list[str]) -> Optional[str]:
    deduped = tuple(dict.fromkeys(value for value in values if value))
    if not deduped:
        return None
    return " | ".join(deduped)


def _no_secret_echo(payload: dict[str, JsonValue]) -> bool:
    serialized = json.dumps(payload, sort_keys=True).lower()
    return not any(marker in serialized for marker in _SECRET_MARKERS)
