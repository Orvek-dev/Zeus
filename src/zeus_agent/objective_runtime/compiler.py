from __future__ import annotations

import hashlib
import re
from typing import Final, Sequence

from zeus_agent.objective_runtime.contracts import (
    VerificationObligation,
    ZeusObjectiveContract,
)

_PROMPT_INJECTION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"\b(?:ignore|disregard|override)\s+(?:all\s+)?"
        r"(?:system|developer|previous|rules|instructions|policy)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:reveal|print|show|expose)\s+(?:the\s+)?(?:hidden\s+|internal\s+)?"
        r"(?:system\s+)?(?:prompt|policy|instructions)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bbypass\s+(?:policy|rules|guardrails|safety)\b", re.IGNORECASE),
    re.compile(r"\bjailbreak\b", re.IGNORECASE),
)
_AUTHORITY_WIDENING_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\bgrant\s+(?:yourself|me|all)\s+(?:admin|root|full|all)\b", re.IGNORECASE),
    re.compile(r"\b(?:widen|expand|increase)\s+authority\b", re.IGNORECASE),
    re.compile(r"\b(?:elevate|escalate)\s+(?:permissions?|privileges?|authority)\b", re.IGNORECASE),
    re.compile(r"\b(?:bypass|ignore)\s+(?:authority|approval|permissions?)\b", re.IGNORECASE),
    re.compile(r"\bfull\s+access\b", re.IGNORECASE),
    re.compile(r"\brun\s+unrestricted\b", re.IGNORECASE),
)
_LIVE_TRANSPORT_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"\benable\s+live\s+transport\b", re.IGNORECASE),
    re.compile(r"\bopen\s+(?:the\s+)?network\b", re.IGNORECASE),
    re.compile(r"\bcall\s+(?:the\s+)?real\s+(?:api|provider|network)\b", re.IGNORECASE),
    re.compile(
        r"\buse\s+(?:the\s+)?(?:production|live|real)\s+"
        r"(?:openai\s+)?(?:endpoint|api|provider|network)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bconnect\s+to\s+(?:mcp|api|plugin|provider)\b", re.IGNORECASE),
)
_SECRET_ASSIGNMENT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(token|api[_-]?key|apikey|password|secret)\s*=\s*\S+"
)
_SECRET_BEARER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(?:authorization\s*:\s*)?bearer\s+[A-Za-z0-9._~+/=-]+"
)
_SECRET_PREFIX_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?i)\b(?:sk-[A-Za-z0-9._-]+|ghp_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|glpat-[A-Za-z0-9_-]+|xox[abp]-[A-Za-z0-9-]+)\b"
)


class ObjectiveCompiler:
    def compile(
        self,
        raw_user_request: str,
        *,
        constraints: Sequence[object] | None = None,
    ) -> ZeusObjectiveContract:
        redacted_request, request_had_secret = _redact_secret_spans(raw_user_request)
        (
            cleaned_constraints,
            constraints_had_secret,
            constraints_malformed,
        ) = _normalize_constraints(constraints)
        normalized = _normalize_text(redacted_request)
        block_reasons = _block_reasons(raw_user_request, cleaned_constraints)
        if request_had_secret or constraints_had_secret:
            block_reasons.append("unsafe_credential_material_detected")
        if constraints_malformed:
            block_reasons.append("malformed_constraint")
        if normalized == "":
            block_reasons.append("empty_objective")

        prompt_injection_detected = "prompt_injection_detected" in block_reasons
        blocked = bool(block_reasons)
        safe_request = "[redacted-prompt-injection]" if prompt_injection_detected else normalized
        safe_objective = "[blocked-prompt-injection]" if prompt_injection_detected else normalized

        return ZeusObjectiveContract(
            objective_id=_objective_id(safe_objective, cleaned_constraints),
            raw_user_request=safe_request,
            normalized_objective=safe_objective,
            deliverables=[] if blocked else [_deliverable_for(safe_objective)],
            constraints=cleaned_constraints,
            authority_posture="blocked" if blocked else "plan_only",
            verification_obligations=_verification_obligations(),
            blocked=blocked,
            status="blocked" if blocked else "compiled",
            block_reasons=_unique(block_reasons),
            prompt_injection_detected=prompt_injection_detected,
            no_secret_echo=True,
        )


def _block_reasons(raw_user_request: str, constraints: Sequence[str]) -> list[str]:
    text = " ".join([raw_user_request, *constraints])
    reasons: list[str] = []
    if _matches_any(text, _PROMPT_INJECTION_PATTERNS):
        reasons.append("prompt_injection_detected")
    if _matches_any(text, _AUTHORITY_WIDENING_PATTERNS):
        reasons.append("authority_widening_requested")
    if _matches_any(text, _LIVE_TRANSPORT_PATTERNS):
        reasons.append("live_transport_enablement_requested")
    return reasons


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) is not None for pattern in patterns)


def _normalize_constraints(constraints: Sequence[object] | None) -> tuple[list[str], bool, bool]:
    cleaned: list[str] = []
    secret_detected = False
    malformed_detected = False
    for item in constraints or ():
        if not isinstance(item, str):
            malformed_detected = True
            continue
        redacted, item_had_secret = _redact_secret_spans(item)
        normalized = _normalize_text(redacted)
        if normalized:
            cleaned.append(normalized)
        secret_detected = secret_detected or item_had_secret
    return cleaned, secret_detected, malformed_detected


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().split())


def _redact_secret_spans(value: str) -> tuple[str, bool]:
    assignment_redacted = _SECRET_ASSIGNMENT_PATTERN.sub(_redact_assignment, value)
    bearer_redacted = _SECRET_BEARER_PATTERN.sub("[redacted-secret]", assignment_redacted)
    prefix_redacted = _SECRET_PREFIX_PATTERN.sub("[redacted-secret]", bearer_redacted)
    return prefix_redacted, prefix_redacted != value


def _redact_assignment(match: re.Match[str]) -> str:
    label = match.group(1)
    return "{0}=[redacted-secret]".format(label)


def _deliverable_for(normalized_objective: str) -> str:
    return "Governed objective contract for: {0}".format(normalized_objective)


def _verification_obligations() -> list[VerificationObligation]:
    return [
        VerificationObligation(
            obligation_id="verify-objective-contract",
            requirement_id="REQ-ZEUS-FINAL-001:S1",
            description="Objective contract contains normalized intent, deliverables, constraints, authority posture, and verification obligations.",
            evidence_target="objective_contract_fields",
        ),
        VerificationObligation(
            obligation_id="verify-fail-closed-inputs",
            requirement_id="REQ-ZEUS-FINAL-007:S1",
            description="Empty, malformed, prompt-injection-like, or authority-widening inputs fail closed.",
            evidence_target="objective_contract_blocks",
        ),
        VerificationObligation(
            obligation_id="verify-no-live-transport-or-secret-echo",
            requirement_id="REQ-ZEUS-FINAL-008:S1",
            description="Live transport and unsafe credential material are blocked before runtime and raw secrets are not echoed.",
            evidence_target="objective_contract_redaction",
        ),
    ]


def _objective_id(normalized_objective: str, constraints: list[str]) -> str:
    digest = hashlib.sha256(
        "\n".join([normalized_objective, *constraints]).encode("utf-8")
    ).hexdigest()
    return "obj-{0}".format(digest[:16])


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
