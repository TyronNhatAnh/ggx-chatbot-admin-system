"""HTTP client for read-only User Service APIs.

Base URL : https://stag-api.gogox.co.kr/user
Swagger  : https://stag-api.gogox.co.kr/user/swagger/index.html

All methods return structured dict payloads and never raise exceptions to the
AI/tool layer.
"""

import logging
import time

import httpx

from app.config import settings
from app.services.auth_token_manager import get_token_manager

logger = logging.getLogger(__name__)

_API_PREFIX = "/api/v1"


class UserServiceClient:
    """Read-only HTTP client for selected User Service endpoints."""

    def __init__(self) -> None:
        self._base_url: str = settings.user_service_base_url.rstrip("/")
        self._token_mgr = get_token_manager()
        self._http = httpx.Client(timeout=10.0)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        requires_auth: bool = True,
    ) -> dict | list:
        headers: dict[str, str] = {}
        if requires_auth:
            self._token_mgr.ensure_token()
            headers = self._token_mgr.bearer_header

        url = f"{self._base_url}{_API_PREFIX}{path}"
        t = time.perf_counter()
        response = self._http.request(method, url, headers=headers, params=params)
        logger.info(
            "[HTTP %s] %s  status=%s  elapsed=%.3fs",
            method,
            url,
            response.status_code,
            time.perf_counter() - t,
        )

        if requires_auth and response.status_code == 401:
            logger.warning("[HTTP %s] 401 on %s - invalidating token and retrying.", method, path)
            self._token_mgr.invalidate()
            self._token_mgr.ensure_token()
            t = time.perf_counter()
            response = self._http.request(method, url, headers=self._token_mgr.bearer_header, params=params)
            logger.info(
                "[HTTP %s] retry %s  status=%s  elapsed=%.3fs",
                method,
                url,
                response.status_code,
                time.perf_counter() - t,
            )

        response.raise_for_status()
        return response.json()

    @staticmethod
    def _unwrap_success_payload(payload: dict | list | object) -> dict | list | object:
        if isinstance(payload, dict):
            if payload.get("success") is False:
                return {"error": "USER_SERVICE_ERROR", "detail": payload.get("errors")}
            return payload.get("data", payload)
        return payload

    def get_withdraw_reasons(self) -> dict:
        """GET /api/v1/withdraw-reasons."""
        try:
            payload = self._request("GET", "/withdraw-reasons", requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            reasons = data if isinstance(data, list) else []
            return {"withdraw_reasons": reasons, "count": len(reasons)}
        except httpx.HTTPStatusError as exc:
            logger.error("get_withdraw_reasons HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_withdraw_reasons network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_withdraw_reasons unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_tos_contents(self) -> dict:
        """GET /api/v1/guest/tos-contents."""
        try:
            payload = self._request("GET", "/guest/tos-contents", requires_auth=False)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            if isinstance(data, list):
                return {"tos_contents": data, "count": len(data)}
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.HTTPStatusError as exc:
            logger.error("get_tos_contents HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_tos_contents network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_tos_contents unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_feature_flags(self) -> dict:
        """GET /api/v1/feature/flag."""
        try:
            payload = self._request("GET", "/feature/flag", requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            if isinstance(data, list):
                return {"feature_flags": data, "count": len(data)}
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.HTTPStatusError as exc:
            logger.error("get_feature_flags HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_feature_flags network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_feature_flags unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_my_feature_flags(self) -> dict:
        """GET /api/v1/auth/feature/flag."""
        try:
            payload = self._request("GET", "/auth/feature/flag", requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            if isinstance(data, list):
                return {"feature_flags": data, "count": len(data), "scope": "current_user"}
            if isinstance(data, dict):
                data["scope"] = "current_user"
                return data
            return {"raw": data, "scope": "current_user"}
        except httpx.HTTPStatusError as exc:
            logger.error("get_my_feature_flags HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_my_feature_flags network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_my_feature_flags unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}


_client: UserServiceClient | None = None


def get_user_client() -> UserServiceClient:
    """Return singleton UserServiceClient."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = UserServiceClient()
    return _client
