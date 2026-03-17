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

    def get_user_profile(self, user_id: int) -> dict:
        """GET /api/v1/users?id={user_id}."""
        try:
            payload = self._request("GET", "/users", params={"id": user_id}, requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data

            user = self._find_user_record(data)
            if not user:
                return {"error": "USER_NOT_FOUND", "user_id": user_id}

            result = self._slim_user_profile(user)
            result["source"] = "GET /api/v1/users?id="
            return result
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "USER_NOT_FOUND", "user_id": user_id}
            logger.error("get_user_profile HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_user_profile network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_user_profile unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_my_user_profile(self) -> dict:
        """GET /api/v1/users/me."""
        try:
            payload = self._request("GET", "/users/me", requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data

            user = self._find_user_record(data)
            if not user:
                return {"error": "USER_NOT_FOUND", "detail": "No current-user profile found"}

            result = self._slim_user_profile(user)
            result["source"] = "GET /api/v1/users/me"
            return result
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "USER_NOT_FOUND"}
            logger.error("get_my_user_profile HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_my_user_profile network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_my_user_profile unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

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

    def search_users(
        self,
        *,
        name: str | None = None,
        phone_number: str | None = None,
        email: str | None = None,
        page_index: int = 1,
        page_size: int = 20,
    ) -> dict:
        """GET /api/v1/users/search."""
        params: dict[str, object] = {"pageIndex": page_index, "pageSize": page_size}
        if name:
            params["name"] = name
        if phone_number:
            params["phoneNumber"] = phone_number
        if email:
            params["email"] = email

        try:
            payload = self._request("GET", "/users/search", params=params, requires_auth=True)
            if isinstance(payload, dict) and payload.get("success") is False:
                return {"error": "USER_SERVICE_ERROR", "detail": payload.get("errors")}

            data = payload.get("data") if isinstance(payload, dict) else payload
            rows = data if isinstance(data, list) else []
            return {
                "users": [self._slim_user_profile(u) for u in rows if isinstance(u, dict)],
                "count": len(rows),
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
        org_name: str | None = None,
        branch_name: str | None = None,
        page_index: int = 1,
        page_size: int = 20,
    ) -> dict:
        """GET /api/v1/branch/search."""
        params: dict[str, object] = {"pageIndex": page_index, "pageSize": page_size}
        if org_name:
            params["orgName"] = org_name
        if branch_name:
            params["branchName"] = branch_name

        try:
            payload = self._request("GET", "/branch/search", params=params, requires_auth=True)
            if isinstance(payload, dict) and payload.get("success") is False:
                return {"error": "USER_SERVICE_ERROR", "detail": payload.get("errors")}
            data = payload.get("data") if isinstance(payload, dict) else payload
            rows = data if isinstance(data, list) else []
            return {"branches": rows, "count": len(rows), "query": params}
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
        organization_name: str | None = None,
        division: str | None = None,
        page_index: int = 1,
        page_size: int = 20,
    ) -> dict:
        """GET /api/v1/organization/search."""
        params: dict[str, object] = {"pageIndex": page_index, "pageSize": page_size}
        if organization_name:
            params["organizationName"] = organization_name
        if division:
            params["division"] = division

        try:
            payload = self._request("GET", "/organization/search", params=params, requires_auth=True)
            if isinstance(payload, dict) and payload.get("success") is False:
                return {"error": "USER_SERVICE_ERROR", "detail": payload.get("errors")}
            data = payload.get("data") if isinstance(payload, dict) else payload
            rows = data if isinstance(data, list) else []
            return {"organizations": rows, "count": len(rows), "query": params}
        except httpx.HTTPStatusError as exc:
            logger.error("search_organizations HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("search_organizations network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("search_organizations unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def verify_client_token(self, token: str) -> dict:
        """GET /api/v1/auth/client-token/verify?token=... (read-only verification)."""
        try:
            payload = self._request("GET", "/auth/client-token/verify", params={"token": token}, requires_auth=False)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            return {"verified": True, "result": data}
        except httpx.HTTPStatusError as exc:
            logger.error("verify_client_token HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc), "verified": False}
        except httpx.RequestError as exc:
            logger.error("verify_client_token network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc), "verified": False}
        except Exception as exc:  # noqa: BLE001
            logger.error("verify_client_token unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc), "verified": False}

    def list_admin_roles(self, department_id: int | None = None) -> dict:
        """GET /api/v1/admin/roles[?departmentId=...]."""
        params = {"departmentId": department_id} if department_id is not None else None
        try:
            payload = self._request("GET", "/admin/roles", params=params, requires_auth=True)
            data = self._unwrap_success_payload(payload)
            rows = data if isinstance(data, list) else []
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
            rows = data if isinstance(data, list) else []
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
            rows = data if isinstance(data, list) else []
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

    def validate_b2c_org_code(self, org_code: str) -> dict:
        """GET /api/v1/auth/b2c/org-code/validate?orgCode=..."""
        try:
            payload = self._request("GET", "/auth/b2c/org-code/validate", params={"orgCode": org_code}, requires_auth=True)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            return {"valid": True, "org_code": org_code, "result": data} if data else {"valid": False, "org_code": org_code}
        except httpx.HTTPStatusError as exc:
            logger.error("validate_b2c_org_code HTTP %s - %s", exc.response.status_code, exc.response.text)
            return {"error": "USER_SERVICE_ERROR", "detail": str(exc), "valid": False}
        except httpx.RequestError as exc:
            logger.error("validate_b2c_org_code network error - %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc), "valid": False}
        except Exception as exc:  # noqa: BLE001
            logger.error("validate_b2c_org_code unexpected error - %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc), "valid": False}

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
