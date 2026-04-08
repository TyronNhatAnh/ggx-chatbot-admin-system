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
from app.limits import MAX_LIST_RESULTS, clamp_list_limit, truncate_list
from app.services.auth_token_manager import bearer_header, ensure_token

logger = logging.getLogger(__name__)

_API_PREFIX = "/api/v1"


class UserServiceClient:
    """Read-only HTTP client for selected User Service endpoints."""

    def __init__(self) -> None:
        self._base_url: str = settings.user_service_base_url.rstrip("/")
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
    def _unwrap_success_payload(payload: dict | list | object) -> dict | list | object:
        if isinstance(payload, dict):
            if payload.get("success") is False:
                return {"error": "USER_SERVICE_ERROR", "detail": payload.get("errors")}
            return payload.get("data", payload)
        return payload

    @staticmethod
    def _find_user_record(data: object) -> dict | None:
        """Best-effort extraction of a user record from varied response shapes."""
        if isinstance(data, dict):
            # Direct user payload
            if any(k in data for k in ("userId", "id", "lastSignIn", "lastAccessedAt")):
                return data

            # Common wrapped payloads
            for key in ("user", "profile", "item", "result"):
                v = data.get(key)
                if isinstance(v, dict):
                    return v

            # List wrappers
            for key in ("users", "data", "items", "results"):
                v = data.get(key)
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    return v[0]

        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]

        return None

    @staticmethod
    def _slim_user_profile(user: dict) -> dict:
        """Normalize user profile fields for chatbot responses."""
        return {
            "userId": user.get("userId") or user.get("id") or user.get("UserID"),
            "name": user.get("name") or user.get("fullName") or user.get("username"),
            "phoneNumber": user.get("phoneNumber") or user.get("mobileNo"),
            "email": user.get("email"),
            "organizationId": user.get("organizationId") or user.get("OrganizationID"),
            "branchId": user.get("branchId") or user.get("BranchID"),
            "status": user.get("status") or user.get("statusCd"),
            "lastSignIn": user.get("lastSignIn") or user.get("LastSignIn"),
            "lastAccessedAt": user.get("lastAccessedAt") or user.get("LastAccessedAt"),
            "loginTypeCd": user.get("loginTypeCd") or user.get("LoginTypeCD"),
            "invalidLoginCount": user.get("invalidLoginCount") or user.get("InvalidLoginCount"),
        }

    def search_users(
        self,
        *,
        keyword: str | None = None,
        organization_id: int | None = None,
        branch_id: int | None = None,
        page_index: int = 1,
        page_size: int = MAX_LIST_RESULTS,
    ) -> dict:
        """GET /api/v1/users/search.

        Actual backend params (Go form tags): keyword, organizationId, branchId.
        """
        params: dict[str, object] = {
            "pageIndex": page_index,
            "pageSize": clamp_list_limit(page_size, default=MAX_LIST_RESULTS),
        }
        if keyword:
            params["keyword"] = keyword
        if organization_id:
            params["organizationId"] = organization_id
        if branch_id:
            params["branchId"] = branch_id

        try:
            payload = self._request("GET", "/users/search", params=params, requires_auth=True)
            if isinstance(payload, dict) and payload.get("success") is False:
                return {"error": "USER_SERVICE_ERROR", "detail": payload.get("errors")}

            data = payload.get("data") if isinstance(payload, dict) else payload
            rows = truncate_list(data)
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            return {
                "users": [self._slim_user_profile(u) for u in rows if isinstance(u, dict)],
                "count": len(rows),
                "total_count": meta.get("totalCount", len(data) if isinstance(data, list) else len(rows)),
                "query": params,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("search_users HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("search_users network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("search_users unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_user_driver(self, user_id: int) -> dict:
        """GET /api/v1/user-driver?id={user_id}."""
        try:
            payload = self._request("GET", "/user-driver", params={"id": user_id}, requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            if isinstance(data, dict):
                return data
            return {"raw": data}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "USER_NOT_FOUND", "user_id": user_id}
            logger.error("get_user_driver HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_user_driver network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_user_driver unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_branch_by_id(self, branch_id: int) -> dict:
        """GET /api/v1/branch?id={branch_id}."""
        try:
            payload = self._request("GET", "/branch", params={"id": branch_id}, requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "BRANCH_NOT_FOUND", "branch_id": branch_id}
            logger.error("get_branch_by_id HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_branch_by_id network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_branch_by_id unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def search_branches(
        self,
        *,
        keyword: str | None = None,
        organization_id: int | None = None,
        page_index: int = 1,
        page_size: int = MAX_LIST_RESULTS,
    ) -> dict:
        """GET /api/v1/branch/search.

        Actual backend params (Go form tags): keyword, organizationId.
        """
        params: dict[str, object] = {
            "pageIndex": page_index,
            "pageSize": clamp_list_limit(page_size, default=MAX_LIST_RESULTS),
        }
        if keyword:
            params["keyword"] = keyword
        if organization_id:
            params["organizationId"] = organization_id

        try:
            payload = self._request("GET", "/branch/search", params=params, requires_auth=True)
            if isinstance(payload, dict) and payload.get("success") is False:
                return {"error": "USER_SERVICE_ERROR", "detail": payload.get("errors")}
            data = payload.get("data") if isinstance(payload, dict) else payload
            rows = truncate_list(data)
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            return {
                "branches": rows,
                "count": len(rows),
                "total_count": meta.get("totalCount", len(data) if isinstance(data, list) else len(rows)),
                "query": params,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("search_branches HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("search_branches network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("search_branches unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_organization_by_id(self, organization_id: int) -> dict:
        """GET /api/v1/organization?id={organization_id}."""
        try:
            payload = self._request("GET", "/organization", params={"id": organization_id}, requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "ORGANIZATION_NOT_FOUND", "organization_id": organization_id}
            logger.error("get_organization_by_id HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_organization_by_id network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_organization_by_id unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def search_organizations(
        self,
        *,
        keyword: str | None = None,
        org_division: str | None = None,
        page_index: int = 1,
        page_size: int = MAX_LIST_RESULTS,
    ) -> dict:
        """GET /api/v1/organization/search.

        Actual backend params (Go form tags): keyword, orgDivision.
        Valid orgDivision values: b2c, b2b, driver, customer.
        """
        params: dict[str, object] = {
            "pageIndex": page_index,
            "pageSize": clamp_list_limit(page_size, default=MAX_LIST_RESULTS),
        }
        if keyword:
            params["keyword"] = keyword
        if org_division:
            params["orgDivision"] = org_division

        try:
            payload = self._request("GET", "/organization/search", params=params, requires_auth=True)
            if isinstance(payload, dict) and payload.get("success") is False:
                return {"error": "USER_SERVICE_ERROR", "detail": payload.get("errors")}
            data = payload.get("data") if isinstance(payload, dict) else payload
            rows = truncate_list(data)
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}
            return {
                "organizations": rows,
                "count": len(rows),
                "total_count": meta.get("totalCount", len(data) if isinstance(data, list) else len(rows)),
                "query": params,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("search_organizations HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("search_organizations network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("search_organizations unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def list_admin_roles(self, department_id: int | None = None) -> dict:
        """GET /api/v1/admin/roles[?departmentId=...]."""
        params = {"departmentId": department_id} if department_id is not None else None
        try:
            payload = self._request("GET", "/admin/roles", params=params, requires_auth=True)
            data = self._unwrap_success_payload(payload)
            rows = truncate_list(data)
            return {"roles": rows, "count": len(rows)}
        except httpx.HTTPStatusError as exc:
            logger.error("list_admin_roles HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("list_admin_roles network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("list_admin_roles unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def list_admin_departments(self) -> dict:
        """GET /api/v1/admin/departments."""
        try:
            payload = self._request("GET", "/admin/departments", requires_auth=True)
            data = self._unwrap_success_payload(payload)
            rows = truncate_list(data)
            return {"departments": rows, "count": len(rows)}
        except httpx.HTTPStatusError as exc:
            logger.error("list_admin_departments HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("list_admin_departments network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("list_admin_departments unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def list_admin_menus(self) -> dict:
        """GET /api/v1/admin/menus."""
        try:
            payload = self._request("GET", "/admin/menus", requires_auth=True)
            data = self._unwrap_success_payload(payload)
            rows = truncate_list(data)
            return {"menus": rows, "count": len(rows)}
        except httpx.HTTPStatusError as exc:
            logger.error("list_admin_menus HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("list_admin_menus network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("list_admin_menus unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_admin_permissions(self, role_id: int) -> dict:
        """GET /api/v1/admin/permissions?roleId=..."""
        try:
            payload = self._request("GET", "/admin/permissions", params={"roleId": role_id}, requires_auth=True)
            data = self._unwrap_success_payload(payload)
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.HTTPStatusError as exc:
            logger.error("get_admin_permissions HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc), "role_id": role_id}
        except httpx.RequestError as exc:
            logger.error("get_admin_permissions network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc), "role_id": role_id}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_admin_permissions unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc), "role_id": role_id}

    def get_accessible_menu_tree(self, role_id: int) -> dict:
        """GET /api/v1/admin/permissions/menus?roleId=..."""
        try:
            payload = self._request("GET", "/admin/permissions/menus", params={"roleId": role_id}, requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, list):
                return {"menus": data, "count": len(data), "role_id": role_id}
            return data if isinstance(data, dict) else {"raw": data, "role_id": role_id}
        except httpx.HTTPStatusError as exc:
            logger.error("get_accessible_menu_tree HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc), "role_id": role_id}
        except httpx.RequestError as exc:
            logger.error("get_accessible_menu_tree network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc), "role_id": role_id}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_accessible_menu_tree unexpected error - %s: %s", type(exc).__name__, exc)

    def verify_biz_registration_number(self, biz_number: str, user_id: int | None = None) -> dict:
        """GET /api/v1/guest/etax/verify_biz_registration_number/{biz_number}[?userId=...]"""
        try:
            path = f"/guest/etax/verify_biz_registration_number/{biz_number}"
            params = {"userId": user_id} if user_id else None
            payload = self._request("GET", path, params=params, requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            return {"valid": True, "biz_number": biz_number, "result": data} if data else {"valid": False, "biz_number": biz_number}
        except httpx.HTTPStatusError as exc:
            logger.error("verify_biz_registration_number HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc), "valid": False}
        except httpx.RequestError as exc:
            logger.error("verify_biz_registration_number network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc), "valid": False}
        except Exception as exc:  # noqa: BLE001
            logger.error("verify_biz_registration_number unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc), "valid": False}


_client: UserServiceClient | None = None


def get_user_client() -> UserServiceClient:
    """Return singleton UserServiceClient."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = UserServiceClient()
    return _client
