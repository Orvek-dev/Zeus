from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Sequence

from .authority import ApprovalReceipt, AuthorityContext
from .capabilities import CapabilityGraph
from .evidence import EvidenceStatus, MnemeEvidenceRecord

DEFAULT_CRITERION_ID = "REQ-ZEUS-KERNEL-006:S1"
_CRITERION_ID_PATTERN = re.compile(r"^REQ-[A-Z0-9-]+-\d{3}(?::S\d+)?$")


class CapabilityBroker:
    def __init__(
        self,
        graph: CapabilityGraph,
        handlers: Dict[str, Callable[[dict], object]],
    ) -> None:
        self._graph = graph
        self._handlers = dict(handlers)
        self.evidence_records: List[MnemeEvidenceRecord] = []

    def dispatch(
        self,
        capability_id: str,
        payload: dict,
        context: AuthorityContext,
        *,
        profile: str = "coding-agent",
        approval_receipts: Optional[Sequence[ApprovalReceipt]] = None,
        criterion_id: str = DEFAULT_CRITERION_ID,
    ) -> dict:
        criterion_id_value = DEFAULT_CRITERION_ID
        if isinstance(criterion_id, str):
            normalized_criterion_id = criterion_id.strip()
            if _CRITERION_ID_PATTERN.fullmatch(normalized_criterion_id):
                criterion_id_value = normalized_criterion_id
        descriptor = self._graph.descriptor_for(capability_id)
        if descriptor is None:
            return self._finalize(
                capability_id=capability_id,
                decision="blocked",
                reason="unknown_capability",
                result=None,
                status=EvidenceStatus.BLOCKED,
                context=context,
                criterion_id=criterion_id_value,
            )

        authority_decision = context.allows(
            capability_id,
            path=self._payload_scope(payload, "path"),
            network_host=self._payload_scope(payload, "network_host"),
            credential_scope=self._payload_scope(payload, "credential_scope"),
        )
        visible_names = {
            entry["function"]["name"]
            for entry in self._graph.compile_model_schema(
                profile=profile,
                authority=context,
                approval_receipts=approval_receipts,
            )
        }
        if descriptor.name not in visible_names:
            return self._finalize(
                capability_id=capability_id,
                decision="blocked",
                reason="capability_not_model_visible",
                result=None,
                status=EvidenceStatus.BLOCKED,
                context=context,
                criterion_id=criterion_id_value,
            )
        if authority_decision.decision != "allowed":
            return self._finalize(
                capability_id=capability_id,
                decision="blocked",
                reason=authority_decision.reason,
                result=None,
                status=EvidenceStatus.BLOCKED,
                context=context,
                criterion_id=criterion_id_value,
            )

        handler = self._handlers.get(capability_id)
        if handler is None:
            return self._finalize(
                capability_id=capability_id,
                decision="error",
                reason="unknown_handler",
                result=None,
                status=EvidenceStatus.FAIL,
                context=context,
                criterion_id=criterion_id_value,
            )
        try:
            handler_result = handler(payload)
        except Exception as exc:
            return self._finalize(
                capability_id=capability_id,
                decision="error",
                reason=str(exc) or "handler_exception",
                result=None,
                status=EvidenceStatus.FAIL,
                context=context,
                criterion_id=criterion_id_value,
            )

        handler_block_reason = self._handler_block_reason(handler_result)
        if handler_block_reason is not None:
            return self._finalize(
                capability_id=capability_id,
                decision="blocked",
                reason=handler_block_reason,
                result=handler_result,
                status=EvidenceStatus.BLOCKED,
                context=context,
                criterion_id=criterion_id_value,
            )

        return self._finalize(
            capability_id=capability_id,
            decision="allowed",
            reason=None,
            result=handler_result,
            status=EvidenceStatus.PASS,
            context=context,
            criterion_id=criterion_id_value,
        )

    @staticmethod
    def _payload_scope(payload: dict, key: str) -> Optional[str]:
        value = payload.get(key)
        if isinstance(value, str):
            return value
        return None

    @staticmethod
    def _handler_block_reason(handler_result: object) -> Optional[str]:
        if not isinstance(handler_result, dict):
            return None
        if handler_result.get("decision") != "blocked":
            return None
        reason = handler_result.get("reason")
        if isinstance(reason, str) and reason.strip():
            return reason
        return "handler_policy_blocked"

    def _finalize(
        self,
        *,
        capability_id: str,
        decision: str,
        reason: Optional[str],
        result: object,
        status: EvidenceStatus,
        context: AuthorityContext,
        criterion_id: str,
    ) -> dict:
        summary_parts = ["decision={0}".format(decision), "capability_id={0}".format(capability_id)]
        if reason is not None:
            summary_parts.append("reason={0}".format(reason))
        record = MnemeEvidenceRecord(
            run_id=context.run_id,
            goal_contract_id=context.goal_contract_id,
            criterion_id=criterion_id,
            evidence_type="capability_dispatch",
            summary=", ".join(summary_parts),
            status=status,
            capability_id=capability_id,
        )
        self.evidence_records.append(record)
        response = {
            "decision": decision,
            "capability_id": capability_id,
            "result": result,
            "evidence": record.model_dump(mode="json"),
        }
        if reason is not None:
            response["reason"] = reason
        return response
