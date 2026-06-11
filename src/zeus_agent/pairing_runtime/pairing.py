from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Final, Optional

from pydantic import JsonValue

from zeus_agent.trust_loop_runtime import SQLiteControlPlaneStore

_CODE_ALPHABET: Final = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L
_MAX_SKEW_SECONDS: Final = 300
_KV_PREFIX: Final = "pair."
_V1_PREFIX: Final = "v1token."


def sign_request(secret: str, timestamp: str, body: bytes) -> str:
    """HMAC-SHA256 over `timestamp.body` — what host adapters send."""
    material = timestamp.encode("utf-8") + b"." + body
    return hmac.new(secret.encode("utf-8"), material, hashlib.sha256).hexdigest()


class PairingManager:
    """Pairing records live in the shared control-plane store.

    The secret is held by the local daemon home (single-operator, local-first
    threat model); what pairing defends against is a REMOTE or injected agent
    silently re-pointing itself at an attacker's policy server, or an
    unpaired process calling decide() at all.
    """

    def __init__(self, store: SQLiteControlPlaneStore) -> None:
        self.store = store

    # ---------------------------------------------------------------- lifecycle
    def request(self, host_name: str) -> dict[str, str]:
        """Agent-side bootstrap: returns the code to SHOW THE HUMAN and the
        secret the adapter keeps. Unusable until the human approves the code."""
        code = "ZEUS-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
        secret = secrets.token_hex(32)
        self.store.kv_set(
            _KV_PREFIX + code,
            json.dumps(
                {
                    "secret": secret,
                    "host": host_name.strip() or "unknown",
                    "status": "pending",
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )
        return {"code": code, "secret": secret}

    def approve(self, code: str) -> bool:
        record = self._load(code)
        if record is None:
            return False
        record["status"] = "approved"
        record["approved_at"] = datetime.now(timezone.utc).isoformat()
        self.store.kv_set(_KV_PREFIX + code.strip().upper(), json.dumps(record))
        return True

    def revoke(self, code: str) -> bool:
        record = self._load(code)
        if record is None:
            return False
        record["status"] = "revoked"
        self.store.kv_set(_KV_PREFIX + code.strip().upper(), json.dumps(record))
        return True

    def status(self, code: str) -> Optional[str]:
        record = self._load(code)
        return str(record["status"]) if record else None

    # ----------------------------------------------------------- /v1 tokens
    # The /v1 proxy is spoken by vanilla LLM SDKs that can only set STATIC
    # headers — per-request HMAC (above) is impossible there, so a static
    # bearer token is the ceiling. Only the sha256 of the token is stored; the
    # token's registration is the SOURCE OF TRUTH for identity, so a forged
    # x-zeus-* header can no longer mis-attribute budget or taint.
    def issue_v1_token(
        self,
        host_name: str,
        *,
        principal_id: Optional[str] = None,
        ttl_days: int = 30,
    ) -> dict[str, str]:
        token = "zv1_" + secrets.token_hex(24)
        host = host_name.strip() or "unknown"
        now = datetime.now(timezone.utc)
        record: dict[str, JsonValue] = {
            "host": host,
            "principal": (principal_id or "agent.{0}".format(host)).strip(),
            "issued_at": now.isoformat(),
            "status": "active",
        }
        if ttl_days > 0:
            record["expires_at"] = (now + timedelta(days=ttl_days)).isoformat()
        self.store.kv_set(_V1_PREFIX + _token_digest(token), json.dumps(record))
        return {
            "token": token,
            "host": host,
            "expires_at": str(record.get("expires_at", "never")),
            "next": "set header `x-zeus-v1-token: {0}` on /v1 requests".format(token),
        }

    def verify_v1_token(
        self, token: Optional[str], *, now: Optional[datetime] = None
    ) -> Optional[dict]:
        if not token or not token.strip():
            return None
        raw = self.store.kv_get(_V1_PREFIX + _token_digest(token.strip()))
        if raw is None:
            return None
        try:
            parsed = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(parsed, dict):
            return None
        if parsed.get("status") == "revoked":
            return None
        expires_at = parsed.get("expires_at")
        if isinstance(expires_at, str) and expires_at:
            try:
                deadline = datetime.fromisoformat(expires_at)
            except ValueError:
                return None  # unparseable expiry → fail closed
            current = now if now is not None else datetime.now(timezone.utc)
            if current >= deadline:
                return None
        return parsed

    def revoke_v1_token(self, token: str) -> bool:
        digest = _token_digest(token.strip())
        raw = self.store.kv_get(_V1_PREFIX + digest)
        if raw is None:
            return False
        try:
            parsed = json.loads(raw)
        except ValueError:
            return False
        if not isinstance(parsed, dict):
            return False
        parsed["status"] = "revoked"
        self.store.kv_set(_V1_PREFIX + digest, json.dumps(parsed))
        return True

    # ------------------------------------------------------------------- verify
    def verify(
        self,
        *,
        code: Optional[str],
        timestamp: Optional[str],
        signature: Optional[str],
        body: bytes,
        now: Optional[datetime] = None,
    ) -> tuple[bool, str]:
        if not code or not timestamp or not signature:
            return False, "pairing_required"
        record = self._load(code)
        if record is None:
            return False, "pairing_unknown"
        if record.get("status") != "approved":
            return False, "pairing_not_approved"
        try:
            stamp = datetime.fromisoformat(timestamp)
        except ValueError:
            return False, "pairing_bad_timestamp"
        current = now if now is not None else datetime.now(timezone.utc)
        if abs((current - stamp).total_seconds()) > _MAX_SKEW_SECONDS:
            return False, "pairing_stale_timestamp"
        expected = sign_request(str(record["secret"]), timestamp, body)
        if not hmac.compare_digest(expected, signature):
            return False, "pairing_bad_signature"
        return True, "ok"

    def _load(self, code: str) -> Optional[dict]:
        raw = self.store.kv_get(_KV_PREFIX + code.strip().upper())
        if raw is None:
            return None
        try:
            parsed = json.loads(raw)
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
