"""HTTP client for read-only Driver Service APIs.

Base URL : https://stag-api.gogox.co.kr/driver
Swagger  : https://stag-api.gogox.co.kr/driver/swagger/index.html

All methods return structured dict payloads and never raise exceptions to the
AI/tool layer.
"""

import logging
import time

import httpx

from app.config import settings
from app.limits import MAX_LIST_RESULTS, clamp_list_limit, truncate_list
from app.services.auth_token_manager import bearer_header, ensure_token

logger = logging.getLogger(__name__)

_API_PREFIX = "/api/v1"


class DriverServiceClient:
    """Read-only HTTP client for selected Driver Service endpoints."""

    def __init__(self) -> None:
        self._base_url: str = settings.driver_service_base_url.rstrip("/")
        self._http = httpx.Client(timeout=10.0)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
        requires_auth: bool = True,
    ) -> dict | list:
        headers: dict[str, str] = {}
        if requires_auth:
            ensure_token()
            headers = bearer_header()

        url = f"{self._base_url}{_API_PREFIX}{path}"
        t = time.perf_counter()
        response = self._http.request(method, url, headers=headers, params=params, json=json)
        logger.info(
            "[HTTP %s] %s  status=%s  elapsed=%.3fs",
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
                return {"error": "DRIVER_SERVICE_ERROR", "detail": payload.get("errors")}
            return payload.get("data", payload)
        return payload

    def get_driver(self, driver_id: int) -> dict:
        """GET /api/v1/driver?id={driver_id}."""
        try:
            payload = self._request("GET", "/driver", params={"id": driver_id}, requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "DRIVER_NOT_FOUND", "driver_id": driver_id}
            logger.error("get_driver HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "DRIVER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_driver network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_driver unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def search_drivers(
        self,
        *,
        keyword: str,
        page_index: int = 1,
        page_size: int = MAX_LIST_RESULTS,
    ) -> dict:
        """GET /api/v1/driver/search?keyword=&pageIndex=&pageSize=."""
        params: dict[str, object] = {
            "keyword": keyword,
            "pageIndex": page_index,
            "pageSize": clamp_list_limit(page_size, default=MAX_LIST_RESULTS),
        }
        try:
            payload = self._request("GET", "/driver/search", params=params, requires_auth=True)
            if isinstance(payload, dict) and payload.get("success") is False:
                return {"error": "DRIVER_SERVICE_ERROR", "detail": payload.get("errors")}
            data = payload.get("data") if isinstance(payload, dict) else payload
            rows = truncate_list(data)
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            return {
                "drivers": rows,
                "count": len(rows),
                "total_count": meta.get("totalCount", len(data) if isinstance(data, list) else len(rows)),
                "query": params,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("search_drivers HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "DRIVER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("search_drivers network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("search_drivers unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_driver_location_history(
        self,
        *,
        driver_user_id: int,
        from_time: str,
        to_time: str,
    ) -> dict:
        """GET /api/v1/driver/location-history?driverUserId=&fromTime=&toTime=.

        Times must be in Seoul timezone, format: 2006-01-02 15:04:05.
        """
        params: dict[str, object] = {
            "driverUserId": driver_user_id,
            "fromTime": from_time,
            "toTime": to_time,
        }
        try:
            payload = self._request("GET", "/driver/location-history", params=params, requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "DRIVER_NOT_FOUND", "driver_user_id": driver_user_id}
            logger.error("get_driver_location_history HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "DRIVER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_driver_location_history network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_driver_location_history unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_driver_price(
        self,
        *,
        order_id: int,
        user_id: int,
    ) -> dict:
        """POST /api/v1/guest/price/{orderId} — calculate fare for driver (guest endpoint, no auth)."""
        try:
            payload = self._request(
                "POST",
                f"/guest/price/{order_id}",
                json={"userId": user_id},
                requires_auth=False,
            )
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.HTTPStatusError as exc:
            logger.error("get_driver_price HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "DRIVER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_driver_price network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_driver_price unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def search_driver_report(
        self,
        *,
        driver_type: str,
        keyword: str,
        page_index: int = 1,
        page_size: int = MAX_LIST_RESULTS,
    ) -> dict:
        """GET /api/v1/driver-report/driver/search?type=&keyword=&pageIndex=&pageSize=.

        driver_type must be one of: normalDriver, externalDriver.
        """
        params: dict[str, object] = {
            "type": driver_type,
            "keyword": keyword,
            "pageIndex": page_index,
            "pageSize": clamp_list_limit(page_size, default=MAX_LIST_RESULTS),
        }
        try:
            payload = self._request(
                "GET",
                "/driver-report/driver/search",
                params=params,
                requires_auth=True,
            )
            if isinstance(payload, dict) and payload.get("success") is False:
                return {"error": "DRIVER_SERVICE_ERROR", "detail": payload.get("errors")}
            data = payload.get("data") if isinstance(payload, dict) else payload
            rows = truncate_list(data)
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            return {
                "drivers": rows,
                "count": len(rows),
                "total_count": meta.get("totalCount", len(data) if isinstance(data, list) else len(rows)),
                "query": params,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("search_driver_report HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "DRIVER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("search_driver_report network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("search_driver_report unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_vehicle_pools(self) -> dict:
        """GET /api/v1/vehicles/vehicle-pools — list all vehicle types and pools."""
        try:
            payload = self._request("GET", "/vehicles/vehicle-pools", requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            return data if isinstance(data, dict) else {"vehicle_pools": data}
        except httpx.HTTPStatusError as exc:
            logger.error("get_vehicle_pools HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "DRIVER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_vehicle_pools network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_vehicle_pools unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}


_client: DriverServiceClient | None = None


def get_driver_client() -> DriverServiceClient:
    """Return singleton DriverServiceClient."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = DriverServiceClient()
    return _client
