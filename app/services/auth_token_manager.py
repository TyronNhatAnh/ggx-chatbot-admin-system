"""Authentication token manager backed by the User Service.

Handles POST /api/v1/auth/login, caches the returned Bearer token,
and re-authenticates automatically when the token is missing or rejected.

All HTTP clients in this process share one singleton instance so that a
single login serves every tool call within the same process lifetime.
"""

import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_LOGIN_PATH = "/api/v1/auth/login"
TOKEN_TTL_SECONDS = 3500  # ~58 min; tokens are usually valid for 1 hour


class AuthTokenManager:
    """
    Manages a Bearer token issued by the User Service.

    - Token is fetched lazily on first use.
    - Callers invoke ``ensure_token()`` before making API requests.
    - Callers invoke ``invalidate()`` on 401 and then ``ensure_token()``
      again to trigger a fresh login (retry-once pattern).
    """

    def __init__(self) -> None:
        self._base_url: str = settings.user_service_base_url.rstrip("/")
        self._phone_number: str = settings.user_service_phone_number
        self._password: str = settings.user_service_password
        self._type_cd: int = settings.user_service_type_cd
        self._auth_mode: str = settings.user_service_auth_mode
        self._access_token: str | None = None
        self._token_expiry: float = 0.0  # unix epoch; 0.0 = no valid token

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def ensure_token(self) -> None:
        """Fetch a new token if one is not cached or has expired."""
        if not self._access_token or time.time() >= self._token_expiry:
            self._login()

    def invalidate(self) -> None:
        """Drop the cached token so the next call to ``ensure_token`` re-logs in."""
        self._access_token = None
        self._token_expiry = 0.0

    @property
    def bearer_header(self) -> dict[str, str]:
        """Return an Authorization header dict ready to pass to httpx."""
        return {"Authorization": f"Bearer {self._access_token}"}

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _login(self) -> None:
        url = f"{self._base_url}{_LOGIN_PATH}"
        logger.info(
            "[Auth    ] POST %s  phoneNumber=%s typeCd=%s mode=%s",
            url, self._phone_number, self._type_cd, self._auth_mode,
        )
        t = time.perf_counter()
        try:
            response = httpx.post(
                url,
                headers={"accept": "application/json", "Content-Type": "application/json"},
                json={
                    "phoneNumber": self._phone_number,
                    "password": self._password,
                    "typeCd": self._type_cd,
                    "mode": self._auth_mode,
                },
                timeout=10.0,
            )
            logger.info(
                "[Auth    ] login response HTTP %s  elapsed=%.3fs  body keys: %s",
                response.status_code,
                time.perf_counter() - t,
                list(response.json().keys()) if response.content else "<empty>",
            )
            response.raise_for_status()
            payload = response.json()
            # Response shape: { "success": true, "data": { "accessToken": "...", "token": "..." }, "errors": null }
            data = payload.get("data") or {}
            token = (
                data.get("accessToken")
                or data.get("access_token")
                or data.get("token")
                or data.get("jwt")
            )
            if not token:
                logger.error(
                    "[Auth    ] could not find token in login response. "
                    "success=%s data keys=%s full payload=%s",
                    payload.get("success"), list(data.keys()), payload,
                )
                raise KeyError(
                    f"No token field found in login response.data. Available keys: {list(data.keys())}"
                )
            self._access_token = token
            self._token_expiry = time.time() + TOKEN_TTL_SECONDS
            logger.info("[Auth    ] login successful — token cached, TTL=%ds.", TOKEN_TTL_SECONDS)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "[Auth    ] login HTTP error %s  elapsed=%.3fs — response body: %s",
                exc.response.status_code, time.perf_counter() - t, exc.response.text,
            )
            raise
        except httpx.RequestError as exc:
            logger.error("[Auth    ] login network error  elapsed=%.3fs — %s", time.perf_counter() - t, exc)
            raise
        except KeyError:
            raise


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: AuthTokenManager | None = None


def get_token_manager() -> AuthTokenManager:
    """Return the shared AuthTokenManager, creating it on first call."""
    global _manager  # noqa: PLW0603
    if _manager is None:
        _manager = AuthTokenManager()
    return _manager
