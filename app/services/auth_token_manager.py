"""Request-scoped admin token manager.

This module intentionally does NOT perform login against User Service.
All downstream service calls must use the admin Bearer token forwarded by
the /chat caller for the current request.
"""

from contextvars import ContextVar, Token

_REQUEST_ADMIN_TOKEN: ContextVar[str | None] = ContextVar("request_admin_token", default=None)


def _normalize_bearer_token(raw_token: str) -> str:
    token = (raw_token or "").strip()
    if token.lower().startswith("bearer "):
        return token[7:].strip()
    return token


class AuthTokenManager:
    """Provides Authorization headers from the current request admin token."""

    def ensure_token(self) -> None:
        """Validate that a request-scoped admin token is available."""
        if not self.using_request_token():
            raise ValueError("Missing admin service token in request context")

    def invalidate(self) -> None:
        """No-op for request-scoped token mode (no internal cache)."""
        return

    @property
    def bearer_header(self) -> dict[str, str]:
        """Return Authorization header for downstream service calls."""
        token = _REQUEST_ADMIN_TOKEN.get()
        if not token:
            raise ValueError("Missing admin service token in request context")
        return {"Authorization": f"Bearer {token}"}

    def using_request_token(self) -> bool:
        """True when request-scoped admin token is active."""
        return bool(_REQUEST_ADMIN_TOKEN.get())


_manager: AuthTokenManager | None = None


def get_token_manager() -> AuthTokenManager:
    """Return shared token manager instance."""
    global _manager  # noqa: PLW0603
    if _manager is None:
        _manager = AuthTokenManager()
    return _manager


def set_request_service_token(token: str) -> Token:
    """Set admin bearer token for current request context."""
    normalized = _normalize_bearer_token(token)
    if not normalized:
        raise ValueError("service_token must not be empty")
    return _REQUEST_ADMIN_TOKEN.set(normalized)


def reset_request_service_token(token_ref: Token) -> None:
    """Clear admin bearer token after request completes."""
    _REQUEST_ADMIN_TOKEN.reset(token_ref)
