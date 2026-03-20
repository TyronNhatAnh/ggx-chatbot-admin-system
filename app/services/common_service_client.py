"""HTTP client for read-only Common Service APIs.

Base URL : https://stag-api.gogox.co.kr/common
Swagger  : https://stag-api.gogox.co.kr/common/swagger/index.html

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


class CommonServiceClient:
    """Read-only HTTP client for selected Common Service endpoints."""

    def __init__(self) -> None:
        self._base_url: str = settings.common_service_base_url.rstrip("/")
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
            ensure_token()
            headers = bearer_header()

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

        response.raise_for_status()
        return response.json()

    @staticmethod
    def _unwrap_success_payload(payload: dict | list | object, service_error: str) -> dict | list | object:
        if isinstance(payload, dict):
            if payload.get("success") is False:
                return {"error": service_error, "detail": payload.get("errors")}
            return payload.get("data", payload)
        return payload

    def get_vehicle_prices(self, *, order_type: str) -> dict:
        """GET /api/v1/vehicles?orderType=..."""
        try:
            payload = self._request(
                "GET",
                "/vehicles",
                params={"orderType": order_type},
                requires_auth=True,
            )
            data = self._unwrap_success_payload(payload, "COMMON_SERVICE_ERROR")
            if isinstance(data, dict) and data.get("error"):
                return data
            rows = truncate_list(data)
            return {"vehicles": rows, "count": len(rows), "order_type": order_type}
        except httpx.HTTPStatusError as exc:
            logger.error("get_vehicle_prices HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "COMMON_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_vehicle_prices network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_vehicle_prices unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_vehicle_pools(self) -> dict:
        """GET /api/v1/vehicles/vehicle-pools."""
        try:
            payload = self._request("GET", "/vehicles/vehicle-pools", requires_auth=True)
            data = self._unwrap_success_payload(payload, "COMMON_SERVICE_ERROR")
            if isinstance(data, dict) and data.get("error"):
                return data
            return data if isinstance(data, dict) else {"vehicle_pools": truncate_list(data)}
        except httpx.HTTPStatusError as exc:
            logger.error("get_vehicle_pools HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "COMMON_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_vehicle_pools network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_vehicle_pools unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_services_by_vehicle_pool(
        self,
        *,
        order_type: str,
        vehicle_pool_id: int,
        region_id: int | None = None,
    ) -> dict:
        """GET /api/v1/vehicles/services?orderType=&vehiclePoolId=&regionId=."""
        params: dict[str, object] = {
            "orderType": order_type,
            "vehiclePoolId": vehicle_pool_id,
        }
        if region_id is not None:
            params["regionId"] = region_id

        try:
            payload = self._request("GET", "/vehicles/services", params=params, requires_auth=True)
            data = self._unwrap_success_payload(payload, "COMMON_SERVICE_ERROR")
            if isinstance(data, dict) and data.get("error"):
                return data
            return data if isinstance(data, dict) else {"services": truncate_list(data), "query": params}
        except httpx.HTTPStatusError as exc:
            logger.error("get_services_by_vehicle_pool HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "COMMON_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_services_by_vehicle_pool network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_services_by_vehicle_pool unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_addresses(
        self,
        *,
        keyword: str,
        user_id: int | None = None,
        page: int = 1,
        size: int = MAX_LIST_RESULTS,
    ) -> dict:
        """GET /api/v1/addresses?keyword=&userId=&page=&size=."""
        params: dict[str, object] = {
            "keyword": keyword,
            "page": max(1, page),
            "size": clamp_list_limit(size, default=MAX_LIST_RESULTS),
        }
        if user_id is not None:
            params["userId"] = user_id

        try:
            payload = self._request("GET", "/addresses", params=params, requires_auth=True)
            if isinstance(payload, dict) and payload.get("success") is False:
                return {"error": "COMMON_SERVICE_ERROR", "detail": payload.get("errors")}

            data = payload.get("data") if isinstance(payload, dict) else payload
            rows = truncate_list(data)
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            paging = payload.get("paging", {}) if isinstance(payload, dict) else {}
            total_count = paging.get("total") or meta.get("totalCount") or (len(data) if isinstance(data, list) else len(rows))
            return {
                "addresses": rows,
                "count": len(rows),
                "total_count": total_count,
                "query": params,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("get_addresses HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "COMMON_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_addresses network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_addresses unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def search_api_addresses(
        self,
        *,
        keyword: str,
        page: int = 1,
        size: int = MAX_LIST_RESULTS,
    ) -> dict:
        """GET /api/v1/addresses/search?keyword=&page=&size=."""
        params: dict[str, object] = {
            "keyword": keyword,
            "page": max(1, page),
            "size": clamp_list_limit(size, default=MAX_LIST_RESULTS),
        }
        try:
            payload = self._request("GET", "/addresses/search", params=params, requires_auth=True)
            data = self._unwrap_success_payload(payload, "COMMON_SERVICE_ERROR")
            if isinstance(data, dict) and data.get("error"):
                return data
            rows = truncate_list(data)
            return {"addresses": rows, "count": len(rows), "query": params}
        except httpx.HTTPStatusError as exc:
            logger.error("search_api_addresses HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "COMMON_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("search_api_addresses network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("search_api_addresses unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def search_api_address_details(self, *, keyword: str, jibun_address: str | None = None) -> dict:
        """GET /api/v1/addresses/search-details?keyword=&jibun_address=."""
        params: dict[str, object] = {"keyword": keyword}
        if jibun_address:
            params["jibun_address"] = jibun_address

        try:
            payload = self._request("GET", "/addresses/search-details", params=params, requires_auth=True)
            data = self._unwrap_success_payload(payload, "COMMON_SERVICE_ERROR")
            if isinstance(data, dict) and data.get("error"):
                return data
            rows = truncate_list(data)
            return {"address_details": rows, "count": len(rows), "query": params}
        except httpx.HTTPStatusError as exc:
            logger.error("search_api_address_details HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "COMMON_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("search_api_address_details network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("search_api_address_details unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def list_guest_ads(self) -> dict:
        """GET /api/v1/guest/ads."""
        try:
            payload = self._request("GET", "/guest/ads", requires_auth=False)
            data = self._unwrap_success_payload(payload, "COMMON_SERVICE_ERROR")
            if isinstance(data, dict) and data.get("error"):
                return data
            rows = truncate_list(data)
            return {"ads": rows, "count": len(rows)}
        except httpx.HTTPStatusError as exc:
            logger.error("list_guest_ads HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "COMMON_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("list_guest_ads network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("list_guest_ads unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def list_home_moving_goods_categories(self) -> dict:
        """GET /api/v1/guest/home-moving/goods-categories."""
        try:
            payload = self._request("GET", "/guest/home-moving/goods-categories", requires_auth=False)
            data = self._unwrap_success_payload(payload, "COMMON_SERVICE_ERROR")
            if isinstance(data, dict) and data.get("error"):
                return data
            rows = truncate_list(data)
            return {"goods_categories": rows, "count": len(rows)}
        except httpx.HTTPStatusError as exc:
            logger.error("list_home_moving_goods_categories HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "COMMON_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("list_home_moving_goods_categories network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("list_home_moving_goods_categories unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def list_home_moving_vehicles(self) -> dict:
        """GET /api/v1/guest/home-moving/vehicles."""
        try:
            payload = self._request("GET", "/guest/home-moving/vehicles", requires_auth=False)
            data = self._unwrap_success_payload(payload, "COMMON_SERVICE_ERROR")
            if isinstance(data, dict) and data.get("error"):
                return data
            return data if isinstance(data, dict) else {"vehicles": truncate_list(data)}
        except httpx.HTTPStatusError as exc:
            logger.error("list_home_moving_vehicles HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "COMMON_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("list_home_moving_vehicles network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("list_home_moving_vehicles unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}


_client: CommonServiceClient | None = None


def get_common_client() -> CommonServiceClient:
    """Return singleton CommonServiceClient."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = CommonServiceClient()
    return _client
