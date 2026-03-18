"""Request-scoped admin token manager.

The admin Bearer token forwarded by the /chat caller is stored per-request
via a ContextVar and retrieved by downstream service clients.
"""

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
