"""Request-scoped admin token manager.

The admin Bearer token forwarded by the /chat caller is stored per-request
via a ContextVar and retrieved by downstream service clients.
"""

import base64
import json
import time as _time
from contextvars import ContextVar, Token

_REQUEST_ADMIN_TOKEN: ContextVar[str | None] = ContextVar("request_admin_token", default=None)


def ensure_token() -> None:
    if not _REQUEST_ADMIN_TOKEN.get():
        raise ValueError("Missing admin service token in request context")


def bearer_header() -> dict[str, str]:
    token = _REQUEST_ADMIN_TOKEN.get()
    if not token:
        raise ValueError("Missing admin service token in request context")
    return {"Authorization": f"Bearer {token}"}


def set_request_service_token(token: str) -> Token:
    normalized = (token or "").strip()
    if normalized.lower().startswith("bearer "):
        normalized = normalized[7:].strip()
    if not normalized:
        raise ValueError("service_token must not be empty")
    return _REQUEST_ADMIN_TOKEN.set(normalized)


def reset_request_service_token(token_ref: Token) -> None:
    _REQUEST_ADMIN_TOKEN.reset(token_ref)


def is_token_expired(token: str) -> bool:
    """Return True if the JWT exp claim is in the past.

    Decodes the payload segment only (no signature verification).
    Returns False when the token is not a valid JWT or has no exp claim,
    so non-JWT tokens pass through and fail at the service call as before.
    """
    try:
        raw = (token or "").strip()
        if raw.lower().startswith("bearer "):
            raw = raw[7:].strip()
        parts = raw.split(".")
        if len(parts) != 3:
            return False
        # base64url padding
        payload_b64 = parts[1]
        padding = (4 - len(payload_b64) % 4) % 4
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * padding))
        exp = payload.get("exp")
        if exp is None:
            return False
        return _time.time() > exp
    except Exception:  # noqa: BLE001
        return False
