"""HTTP client for the Order Service API.

Base URL : https://stag-api.gogox.co.kr/order
Swagger  : https://stag-api.gogox.co.kr/order/swagger/index.html

All requests are authenticated via a Bearer token obtained from the
User Service through ``AuthTokenManager``.  The client is read-only —
it only issues GET requests.
"""

import logging

import httpx

from app.config import settings
from app.services.auth_token_manager import get_token_manager

logger = logging.getLogger(__name__)

# API path prefix used by every Order Service endpoint.
_API_PREFIX = "/api/v1"


class OrderServiceClient:
    """
    Read-only HTTP client for the GogoX Order Service.

    Authentication is delegated to ``AuthTokenManager`` so the token is
    shared with any other service client in this process.

    Error handling contract:
    - 404  → structured {"error": "ORDER_NOT_FOUND", ...}
    - 401  → token refreshed and request retried once
    - network error → {"error": "NETWORK_ERROR", ...}
    - anything else → {"error": "ORDER_SERVICE_ERROR", ...}
    Never raises to the tool / AI layer.
    """

    def __init__(self) -> None:
        self._base_url: str = settings.order_service_base_url.rstrip("/")
        self._token_mgr = get_token_manager()

    # ------------------------------------------------------------------
    # Internal GET with automatic token refresh on 401
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        """
        Issue an authenticated GET to ``{base_url}/api/v1{path}``.

        Retries once after re-authentication on HTTP 401.
        Raises ``httpx.HTTPStatusError`` or ``httpx.RequestError`` on failure.
        """
        self._token_mgr.ensure_token()
        url = f"{self._base_url}{_API_PREFIX}{path}"
        logger.info("OrderServiceClient: GET %s  params=%s", url, params)

        response = httpx.get(
            url, headers=self._token_mgr.bearer_header, params=params, timeout=10.0
        )
        logger.info("OrderServiceClient: response HTTP %s for %s", response.status_code, url)

        if response.status_code == 401:
            logger.warning(
                "OrderServiceClient: 401 on %s — refreshing token and retrying.", path
            )
            self._token_mgr.invalidate()
            self._token_mgr.ensure_token()
            response = httpx.get(
                url, headers=self._token_mgr.bearer_header, params=params, timeout=10.0
            )
            logger.info(
                "OrderServiceClient: retry response HTTP %s for %s", response.status_code, url
            )

        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Public API methods (read-only)
    # ------------------------------------------------------------------

    def get_order(self, order_id: str) -> dict:
        """
        Fetch B2C detail for a single order.

        Endpoint: GET /api/v1/orders/{orderId}
        Response shape: { "success": true, "data": {...}, "errors": null }
        """
        try:
            payload = self._get(f"/orders/{order_id}")
            if isinstance(payload, dict):
                if not payload.get("success", True):
                    logger.error("get_order: success=false for order_id=%s — %s", order_id, payload.get("errors"))
                    return {"error": "ORDER_SERVICE_ERROR", "detail": payload.get("errors")}
                return payload.get("data") or payload
            return payload
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "ORDER_NOT_FOUND", "order_id": order_id}
            logger.error(
                "get_order HTTP %s for order_id=%s — body: %s",
                exc.response.status_code, order_id, exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_order network error for order_id=%s — %s", order_id, exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "get_order unexpected error for order_id=%s — %s: %s",
                order_id, type(exc).__name__, exc,
            )
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def search_orders(self, status: str) -> dict:
        """
        List orders filtered by status code.

        Endpoint: GET /api/v1/orders?statusCd={status}
        Response shape: { "success": true, "data": [...] or {...}, "errors": null }
        Valid status values: Pending, Active, Completed, Incompleted,
        Cancelled, Return, WaitingForPayment, Transit.
        Returns {"orders": [...], "count": N}.
        """
        try:
            payload = self._get("/orders", params={"statusCd": status})
            if isinstance(payload, dict):
                if not payload.get("success", True):
                    logger.error("search_orders: success=false statusCd=%s — %s", status, payload.get("errors"))
                    return {"error": "ORDER_SERVICE_ERROR", "detail": payload.get("errors")}
                data = payload.get("data", payload)
            else:
                data = payload
            if isinstance(data, list):
                return {"orders": data, "count": len(data)}
            # data is a wrapper dict e.g. {"orders": [...], "total": N}
            orders = data.get("data") or data.get("orders") or []
            count = data.get("total") or data.get("count") or len(orders)
            return {"orders": orders, "count": count}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "search_orders HTTP %s for statusCd=%s — body: %s",
                exc.response.status_code, status, exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("search_orders network error statusCd=%s — %s", status, exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "search_orders unexpected error statusCd=%s — %s: %s",
                status, type(exc).__name__, exc,
            )
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_delayed_orders(self) -> dict:
        """
        List all orders currently in Transit (in-transit / delayed).

        Endpoint: GET /api/v1/orders?statusCd=Transit
        Response shape: { "success": true, "data": [...] or {...}, "errors": null }
        Returns {"delayed_orders": [...], "count": N}.
        """
        try:
            payload = self._get("/orders", params={"statusCd": "Transit"})
            if isinstance(payload, dict):
                if not payload.get("success", True):
                    logger.error("get_delayed_orders: success=false — %s", payload.get("errors"))
                    return {"error": "ORDER_SERVICE_ERROR", "detail": payload.get("errors")}
                data = payload.get("data", payload)
            else:
                data = payload
            orders = data if isinstance(data, list) else (data.get("data") or data.get("orders") or [])
            return {"delayed_orders": orders, "count": len(orders)}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "get_delayed_orders HTTP %s — body: %s",
                exc.response.status_code, exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_delayed_orders network error — %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "get_delayed_orders unexpected error — %s: %s", type(exc).__name__, exc
            )
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_client: OrderServiceClient | None = None


def get_order_client() -> OrderServiceClient:
    """Return the shared OrderServiceClient instance, creating it on first call."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = OrderServiceClient()
    return _client
