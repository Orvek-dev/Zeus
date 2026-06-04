from __future__ import annotations

import hashlib
import json
import re
from typing import Final

from zeus_agent.security.credentials import redact_secret_spans

HASH_PREFIX: Final = "sha256:"
_SK_REDACTED_PREFIX: Final = "sk-...redacted"
_PERSISTED_SECRET: Final = "[redacted-secret]"
_SECRET_IDENTIFIER_PREFIXES: Final = ("ghp_", "github_pat_", "glpat-", "xoxa-", "xoxb-", "xoxp-")
_SECRET_IDENTIFIER_MARKERS: Final = (
    "api-key=",
    "api_key=",
    "apikey=",
    "bearer ",
    "password=",
    "private-key=",
    "private_key=",
    "secret=",
    "token=",
    "-----begin",
)
_SECRET_IDENTIFIER_PATTERN: Final = re.compile(r"(?i)(^|[^a-z0-9])sk-[A-Za-z0-9][A-Za-z0-9._-]*")
_SECRET_PROVIDER_IDENTIFIER_PATTERN: Final = re.compile(
    r"(?i)(^|[^a-z0-9])(ghp_|github_pat_|glpat-|xoxa-|xoxb-|xoxp-)[A-Za-z0-9][A-Za-z0-9._-]*"
)


def stable_hash(value: str) -> str:
    return HASH_PREFIX + hashlib.sha256(value.encode("utf-8")).hexdigest()


def persisted_message(value: str) -> str:
    return redact_secret_spans(value).replace(_SK_REDACTED_PREFIX, _PERSISTED_SECRET)


def persisted_audit_identity(value: str) -> str:
    if is_secret_like_identifier(value):
        return _PERSISTED_SECRET
    return persisted_message(value)


def is_secret_like_identifier(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized.startswith(_SECRET_IDENTIFIER_PREFIXES):
        return True
    if _SECRET_IDENTIFIER_PATTERN.search(value) is not None:
        return True
    if _SECRET_PROVIDER_IDENTIFIER_PATTERN.search(value) is not None:
        return True
    return any(marker in normalized for marker in _SECRET_IDENTIFIER_MARKERS)


def require_public_identifier(value: str, field_name: str) -> str:
    if is_secret_like_identifier(value):
        raise ValueError("{0}_secret_like_forbidden".format(field_name))
    return value


def gateway_request_hash(
    session_id: str,
    run_id: str,
    goal_contract_id: str,
    resume_token_hash: str,
    message: str,
    authority_fingerprint: str,
) -> str:
    payload = json.dumps(
        [
            session_id,
            run_id,
            goal_contract_id,
            resume_token_hash,
            message,
            authority_fingerprint,
        ],
        separators=(",", ":"),
    )
    return stable_hash(payload)
