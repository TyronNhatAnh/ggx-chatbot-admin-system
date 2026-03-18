"""HTTP client for the Order Service API.

Base URL : https://stag-api.gogox.co.kr/order
Swagger  : https://stag-api.gogox.co.kr/order/swagger/index.html

All requests are authenticated via an admin Bearer token forwarded from
the /chat request context through ``AuthTokenManager``. The client is
read-only from a business perspective — it only queries and calculates data.
"""

import logging
import time
from datetime import date, timedelta

import httpx

from app.config import settings
from app.services.auth_token_manager import bearer_header, ensure_token

logger = logging.getLogger(__name__)

# API path prefix used by every Order Service endpoint.
_API_PREFIX = "/api/v1"


class OrderServiceClient:
    """
    Read-only HTTP client for the GogoX Order Service.

    Authentication is delegated to ``AuthTokenManager`` using the
    request-scoped admin token set by the /chat handler.

    Error handling contract:
    - 404  → structured {"error": "ORDER_NOT_FOUND", ...}
    - 401  → returned as ORDER_SERVICE_ERROR (token must be provided by caller)
    - network error → {"error": "NETWORK_ERROR", ...}
    - anything else → {"error": "ORDER_SERVICE_ERROR", ...}
    Never raises to the tool / AI layer.
    """

    def __init__(self) -> None:
        self._base_url: str = settings.order_service_base_url.rstrip("/")
        # Persistent session — reuses TCP connections across tool calls.
        self._http = httpx.Client(timeout=10.0)

    # ------------------------------------------------------------------
    # Internal HTTP helpers with optional auth
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        requires_auth: bool = True,
    ) -> dict | list:
        """Issue an HTTP request to ``{base_url}/api/v1{path}``.

        If ``requires_auth`` is true, uses request-scoped admin token.
        Raises ``httpx.HTTPStatusError`` or ``httpx.RequestError`` on failure.
        """
        headers: dict[str, str] = {}
        if requires_auth:
            ensure_token()
            headers = bearer_header()

        url = f"{self._base_url}{_API_PREFIX}{path}"
        logger.info("[HTTP %s] %s  params=%s", method, url, params)
        t = time.perf_counter()

        response = self._http.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
        )
        logger.info(
            "[HTTP %s] %s  status=%s  elapsed=%.3fs",
            method,
            url,
            response.status_code,
            time.perf_counter() - t,
        )

        response.raise_for_status()
        return response.json()

    def _get(self, path: str, params: dict | None = None) -> dict | list:
        """
        Issue an authenticated GET to ``{base_url}/api/v1{path}``.

        Raises ``httpx.HTTPStatusError`` or ``httpx.RequestError`` on failure.
        """
        return self._request("GET", path, params=params, requires_auth=True)

    def _post(
        self,
        path: str,
        *,
        json_body: dict | None = None,
        requires_auth: bool = False,
    ) -> dict | list:
        """Issue a POST request to ``{base_url}/api/v1{path}``."""
        return self._request(
            "POST",
            path,
            json_body=json_body,
            requires_auth=requires_auth,
        )

    @staticmethod
    def _slim_place(place: object) -> object:
        """Keep place payload small to reduce LLM token usage."""
        if place is None:
            return None
        if isinstance(place, str):
            return place
        if not isinstance(place, dict):
            return str(place)

        return {
            "name": (
                place.get("name")
                or place.get("displayName")
                or place.get("title")
                or place.get("fullAddress")
                or place.get("address")
            ),
            "address": place.get("fullAddress") or place.get("address"),
        }

    @staticmethod
    def _first_dict(value: object) -> dict | None:
        """Return a dict payload from either dict or list[dict] shapes."""
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    return item
        return None

    @staticmethod
    def _slim_driver(driver: dict | None) -> dict | None:
        if not driver:
            return None
        return {
            "driverId": driver.get("driverId") or driver.get("id"),
            "name": driver.get("driverName") or driver.get("name") or driver.get("username"),
        }

    @staticmethod
    def _slim_vehicle(vehicle: object) -> dict | None:
        """Normalize vehicle payload for direct user-facing answers."""
        if not isinstance(vehicle, dict):
            return None

        normalized = {
            "vehiclePoolId": vehicle.get("vehiclePoolId") or vehicle.get("id"),
            "name": vehicle.get("vehiclePoolName") or vehicle.get("name"),
            "title": vehicle.get("vehiclePoolTitle") or vehicle.get("title"),
        }
        if all(value is None or value == "" for value in normalized.values()):
            return None
        return normalized

    @staticmethod
    def _slim_calculation_price(price: object) -> dict | None:
        """Keep key pricing components used in user-facing explanations."""
        if not isinstance(price, dict):
            return None

        keys = (
            "baseFee",
            "couponDiscount",
            "clientBonus",
            "consignment",
            "express",
            "preVatFee",
            "vatAmount",
            "cashBackFee",
            "cancellationFee",
            "total",
        )
        slim = {k: price.get(k) for k in keys if k in price}
        return slim or None

    @staticmethod
    def _slim_payment(order: dict) -> dict | None:
        """Build a stable payment summary from order-level and payment rows."""
        if not isinstance(order, dict):
            return None

        payment = (
            OrderServiceClient._first_dict(order.get("paymentInfo"))
            or OrderServiceClient._first_dict(order.get("orderPaymentInfo"))
            or {}
        )

        method = (
            order.get("payCDTitle")
            or order.get("payCdTitle")
            or payment.get("payCdTitle")
            or payment.get("payCDTitle")
            or order.get("payCd")
            or payment.get("payCd")
            or payment.get("method")
        )

        normalized = {
            "method": method,
            "status": payment.get("status") or payment.get("action"),
            "amount": payment.get("amount") or order.get("calculationPrice", {}).get("total"),
        }
        if all(value is None or value == "" for value in normalized.values()):
            return None
        return normalized

    @staticmethod
    def _slim_payment_rows(order: dict, limit: int = 3) -> list[dict]:
        """Expose compact payment rows for payment troubleshooting questions."""
        if not isinstance(order, dict):
            return []

        rows = order.get("paymentInfo") or order.get("orderPaymentInfo") or []
        if not isinstance(rows, list):
            return []

        normalized: list[dict] = []
        for row in rows[:limit]:
            if not isinstance(row, dict):
                continue
            item = {
                "action": row.get("action"),
                "status": row.get("status"),
                "amount": row.get("amount"),
                "paymentType": row.get("paymentType"),
                "orderPaymentId": row.get("orderPaymentId") or row.get("orderId"),
                "approveNo": row.get("approveNo"),
                "receiptUrl": row.get("receiptUrl"),
                "errorCode": row.get("errorCode"),
                "errorMessage": row.get("errorMessage"),
            }
            if any(v not in (None, "") for v in item.values()):
                normalized.append(item)
        return normalized

    @staticmethod
    def _slim_order_owner(owner: object) -> dict | None:
        if not isinstance(owner, dict):
            return None
        normalized = {
            "organizationId": owner.get("OrganizationID") or owner.get("organizationId"),
            "branchId": owner.get("BranchID") or owner.get("branchId"),
            "userId": owner.get("UserID") or owner.get("userId"),
            "name": owner.get("Name") or owner.get("name"),
            "contactNo": owner.get("ContactNo") or owner.get("contactNo"),
            "organizationName": owner.get("OrganizationName") or owner.get("organizationName"),
            "branchName": owner.get("BranchName") or owner.get("branchName"),
        }
        if all(v in (None, "") for v in normalized.values()):
            return None
        return normalized

    @staticmethod
    def _slim_waypoints(waypoints: object, limit: int = 4) -> list[dict]:
        if not isinstance(waypoints, list):
            return []
        result: list[dict] = []
        for wp in waypoints[:limit]:
            if not isinstance(wp, dict):
                continue
            item = {
                "arrangement": wp.get("arrangement"),
                "status": wp.get("statusCd") or wp.get("status"),
                "requestedAt": wp.get("requestedAt"),
                "reachedAt": wp.get("reachedAt"),
                "name": wp.get("name"),
                "mobileNo": wp.get("mobileNo"),
                "address1": wp.get("address1"),
                "address2": wp.get("address2"),
                "lat": wp.get("lat"),
                "lon": wp.get("lon"),
                "distance": wp.get("distance"),
            }
            if any(v not in (None, "") for v in item.values()):
                result.append(item)
        return result

    @staticmethod
    def _slim_goods_item(item: object) -> dict | None:
        """Normalize a single goods item into a compact, stable shape."""
        if not isinstance(item, dict):
            return None

        name = item.get("name") or item.get("title") or item.get("fullName")
        quantity = item.get("quantity")
        remark = item.get("remark")

        # Ignore placeholder rows like {"name": "", "quantity": 0}.
        if (name is None or name == "") and (quantity is None or quantity == 0):
            return None

        normalized = {
            "name": name,
            "quantity": quantity,
            "remark": remark,
        }
        if all(value is None or value == "" for value in normalized.values()):
            return None
        return normalized

    @staticmethod
    def _slim_goods_infos(goods_infos: object) -> list[dict]:
        """Extract goods from list payloads that already contain goodsInfos."""
        if not isinstance(goods_infos, list):
            return []

        goods: list[dict] = []
        seen: set[tuple[object, object, object]] = set()
        for item in goods_infos[:10]:
            slim_item = OrderServiceClient._slim_goods_item(item)
            if not slim_item:
                continue
            key = (slim_item.get("name"), slim_item.get("quantity"), slim_item.get("remark"))
            if key in seen:
                continue
            seen.add(key)
            goods.append(slim_item)

        return goods

    @staticmethod
    def _slim_goods(waypoints: object, applied_extra: object) -> list[dict]:
        """Extract goods from waypoint goods and applied extras (fallback)."""
        goods: list[dict] = []

        if isinstance(waypoints, list):
            for wp in waypoints[:10]:
                if not isinstance(wp, dict):
                    continue
                waypoint_goods = wp.get("goods")
                if not isinstance(waypoint_goods, list):
                    continue
                for raw_item in waypoint_goods[:10]:
                    slim_item = OrderServiceClient._slim_goods_item(raw_item)
                    if slim_item:
                        goods.append(slim_item)

        # Fallback for cases where waypoint goods are empty but applied extra carries goods info.
        if not goods and isinstance(applied_extra, list):
            for extra in applied_extra[:10]:
                if not isinstance(extra, dict):
                    continue
                slim_item = OrderServiceClient._slim_goods_item(extra)
                if slim_item:
                    goods.append(slim_item)

        deduped: list[dict] = []
        seen: set[tuple[object, object, object]] = set()
        for item in goods:
            key = (item.get("name"), item.get("quantity"), item.get("remark"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        return deduped

    @staticmethod
    def _extract_price_total(price_obj: object) -> object:
        """Extract numeric total from a calculationPrice dict; return scalars as-is."""
        if isinstance(price_obj, dict):
            return (
                price_obj.get("total")
                if price_obj.get("total") is not None
                else price_obj.get("subTotal") if price_obj.get("subTotal") is not None
                else price_obj.get("amount")
            )
        return price_obj

    @staticmethod
    def _slim_order(o: dict) -> dict:
        """Slim fields for list results — enough for Gemini to answer location/driver/price
        questions without needing a follow-up get_order call."""
        driver = OrderServiceClient._first_dict(o.get("driver"))
        raw_price = o.get("calculationPrice") if o.get("calculationPrice") is not None else (
            o.get("price") if o.get("price") is not None else
            o.get("totalPrice") if o.get("totalPrice") is not None else
            o.get("amount")
        )
        return {
            "orderId": o.get("orderId") or o.get("id"),
            "status": o.get("statusCd") or o.get("status"),
            "payCd": o.get("payCd"),
            "payMethod": o.get("payCDTitle") or o.get("payCdTitle"),
            "createdAt": o.get("createdAt"),
            "appointmentAt": o.get("appointmentAt"),
            "price": OrderServiceClient._extract_price_total(raw_price),
            "calculationPrice": OrderServiceClient._slim_calculation_price(o.get("calculationPrice")),
            "driverFee": o.get("driverFee") if o.get("driverFee") is not None else (
                o.get("driver_price") if o.get("driver_price") is not None else o.get("driverAmount")
            ),
            "fromPlace": OrderServiceClient._slim_place(o.get("fromPlace")),
            "toPlace": OrderServiceClient._slim_place(o.get("toPlace")),
            "fromAddress": o.get("fromAddress"),
            "toAddress": o.get("toAddress"),
            "driver": OrderServiceClient._slim_driver(driver),
            "vehicle": OrderServiceClient._slim_vehicle(o.get("vehicle")),
            "goods": OrderServiceClient._slim_goods_infos(o.get("goodsInfos")),
            "payment": OrderServiceClient._slim_payment(o),
        }

    @staticmethod
    def _slim_order_detail(o: dict) -> dict:
        """Slim fields for a single order detail — keeps essential info only."""
        if not isinstance(o, dict):
            return {"error": "ORDER_SERVICE_ERROR", "detail": "Invalid order payload format"}

        driver = OrderServiceClient._first_dict(o.get("driver"))
        raw_rows = o.get("priceList") or o.get("fees") or o.get("priceFees") or []
        price_breakdown: list[dict] = []
        if isinstance(raw_rows, list):
            for row in raw_rows[:12]:
                slim = OrderServiceClient._normalize_price_row(row)
                if slim:
                    price_breakdown.append(slim)

        # If priceList-style breakdown is empty, expand calculationPrice fields
        # (baseFee, couponDiscount, vatAmount, total, etc.) as structured breakdown rows.
        calc = o.get("calculationPrice")
        if not price_breakdown and isinstance(calc, dict):
            _CALC_LABELS = {
                "baseFee": "Base fee",
                "express": "Express surcharge",
                "consignment": "Consignment fee",
                "vatAmount": "VAT",
                "couponDiscount": "Coupon discount",
                "clientBonus": "Client bonus",
                "cashBackFee": "Cashback",
                "cancellationFee": "Cancellation fee",
                "preVatFee": "Pre-VAT fee",
                "total": "Total",
            }
            for key, label in _CALC_LABELS.items():
                val = calc.get(key)
                if val is not None and val != 0:
                    price_breakdown.append({"label": label, "amount": val})

        return {
            "orderId": o.get("id") or o.get("orderId"),
            "status": o.get("statusCd"),
            "payCd": o.get("payCd"),
            "payMethod": o.get("payCDTitle") or o.get("payCdTitle"),
            "orderType": o.get("orderType"),
            "isExpress": o.get("isExpress"),
            "createdAt": o.get("createdAt"),
            "updatedAt": o.get("updatedAt"),
            "appointmentAt": o.get("appointmentAt"),
            "completedAt": o.get("completedAt"),
            "cancelledAt": o.get("cancelledAt"),
            "notes": o.get("notes") or o.get("remark"),
            "waypointCount": o.get("waypointCount"),
            "price": OrderServiceClient._extract_price_total(o.get("calculationPrice")),
            "calculationPrice": OrderServiceClient._slim_calculation_price(o.get("calculationPrice")),
            "priceBreakdown": price_breakdown,
            "driverFee": o.get("driverFee") or o.get("driver_price") or o.get("driverAmount"),
            "fromPlace": OrderServiceClient._slim_place(o.get("fromPlace")),
            "toPlace": OrderServiceClient._slim_place(o.get("toPlace")),
            "fromAddress": o.get("fromAddress"),
            "toAddress": o.get("toAddress"),
            "fromAddressDetail": o.get("fromAddressDetail"),
            "toAddressDetail": o.get("toAddressDetail"),
            "driver": OrderServiceClient._slim_driver(driver),
            "vehicle": OrderServiceClient._slim_vehicle(o.get("vehicle")),
            "orderOwner": OrderServiceClient._slim_order_owner(o.get("orderOwner")),
            "goods": OrderServiceClient._slim_goods(
                o.get("waypoints"),
                o.get("appliedExtra"),
            ),
            "waypoints": OrderServiceClient._slim_waypoints(o.get("waypoints")),
            "orderFlags": o.get("orderFlags") if isinstance(o.get("orderFlags"), list) else [],
            "payment": OrderServiceClient._slim_payment(o),
            "paymentInfo": OrderServiceClient._slim_payment_rows(o),
        }

    @staticmethod
    def _normalize_price_row(row: dict) -> dict | None:
        if not isinstance(row, dict):
            return None
        # Use explicit None checks so zero-amount rows (discounts, free items) are preserved.
        _missing = object()
        label = next(
            (row[k] for k in ("label", "name", "title", "type", "feeType") if row.get(k) is not None),
            None,
        )
        amount = next(
            (row[k] for k in ("amount", "price", "value", "fee", "total") if row.get(k) is not None),
            _missing,
        )
        amount = None if amount is _missing else amount
        normalized = {"label": label, "amount": amount}
        if normalized["label"] is None and normalized["amount"] is None:
            return None
        return normalized

    @staticmethod
    def _slim_price_result(data: dict | list | object) -> dict:
        """Normalize estimate/calc-price payloads into a compact stable shape."""
        if not isinstance(data, dict):
            return {"error": "ORDER_SERVICE_ERROR", "detail": "Invalid price payload format"}

        body = data.get("order") if isinstance(data.get("order"), dict) else data
        calculation = body.get("calculationPrice") if isinstance(body, dict) else None

        base_price = (
            body.get("basePrice")
            or body.get("price")
            or body.get("total")
            or body.get("amount")
            or (calculation.get("total") if isinstance(calculation, dict) else None)
        )

        raw_rows = (
            body.get("breakdown")
            or body.get("priceList")
            or body.get("fees")
            or body.get("priceFees")
            or []
        )
        breakdown: list[dict] = []
        if isinstance(raw_rows, list):
            for row in raw_rows[:12]:
                slim = OrderServiceClient._normalize_price_row(row)
                if slim:
                    breakdown.append(slim)

        result: dict = {
            "basePrice": base_price,
            "breakdown": breakdown,
        }

        if isinstance(data.get("driverInfo"), dict):
            driver = data["driverInfo"]
            result["driver"] = {
                "driverId": driver.get("driverId") or driver.get("id"),
                "name": driver.get("driverName") or driver.get("name"),
            }

        if body.get("currency"):
            result["currency"] = body.get("currency")

        return result

    @staticmethod
    def _unwrap_success_payload(payload: dict | list | object) -> dict | list | object:
        """Unwrap {success,data,errors} envelopes while preserving failures."""
        if not isinstance(payload, dict):
            return payload
        if not payload.get("success", True):
            return {"error": "ORDER_SERVICE_ERROR", "detail": payload.get("errors")}
        return payload.get("data", payload)

    @staticmethod
    def _clean_query_params(params: dict | None) -> dict:
        """Drop empty query params to keep requests compact and deterministic."""
        if not isinstance(params, dict):
            return {}
        return {
            key: value
            for key, value in params.items()
            if value is not None and value != "" and value != []
        }

    @staticmethod
    def _normalize_date_yyyy_mm_dd(value: object) -> str | None:
        """Normalize common date inputs to YYYY-MM-DD accepted by report APIs."""
        if not isinstance(value, str):
            return None
        raw = value.strip()
        if not raw:
            return None

        # Accept YYYY-MM-DD, YYYY/MM/DD, and datetime forms like YYYY-MM-DDTHH:MM:SS.
        token = raw.split("T", 1)[0].replace("/", "-")
        parts = token.split("-")
        if len(parts) != 3:
            return None
        y, m, d = parts
        if len(y) == 4 and m.isdigit() and d.isdigit():
            try:
                parsed = date(int(y), int(m), int(d))
                return parsed.isoformat()
            except ValueError:
                return None
        return None

    @staticmethod
    def _normalize_report_pay_values(value: object) -> list[str]:
        """Normalize pay filters to accepted report values."""
        allowed = {"cash", "credit", "card", "point", "brandpay"}

        if value is None:
            return sorted(allowed)

        raw_items: list[str] = []
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"", "all", "*"}:
                return sorted(allowed)
            raw_items = [item.strip().lower() for item in text.split(",") if item.strip()]
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    raw_items.append(item.strip().lower())

        normalized: list[str] = []
        for item in raw_items:
            mapped = "brandpay" if item == "brandPay" else item
            if mapped in allowed and mapped not in normalized:
                normalized.append(mapped)

        return normalized or sorted(allowed)

    def _normalize_report_params(self, params: dict | None) -> dict:
        """Guarantee required query params for statement-of-use report endpoints."""
        source = params if isinstance(params, dict) else {}
        normalized = dict(source)

        today = date.today()
        default_from = (today - timedelta(days=2)).isoformat()
        default_to = today.isoformat()

        from_date = (
            self._normalize_date_yyyy_mm_dd(source.get("fromDate"))
            or self._normalize_date_yyyy_mm_dd(source.get("from_date"))
            or default_from
        )
        to_date = (
            self._normalize_date_yyyy_mm_dd(source.get("toDate"))
            or self._normalize_date_yyyy_mm_dd(source.get("to_date"))
            or default_to
        )

        pay = self._normalize_report_pay_values(source.get("pay"))

        normalized["fromDate"] = from_date
        normalized["toDate"] = to_date
        normalized["pay"] = pay

        # Normalize orgId: accept orgId or org_id.
        org_id = source.get("orgId") or source.get("org_id")
        if org_id is not None:
            try:
                normalized["orgId"] = int(org_id)
            except (TypeError, ValueError):
                logger.warning("Invalid orgId value %r — ignoring", org_id)
            normalized.pop("org_id", None)

        # Remove snake_case aliases if present.
        normalized.pop("from_date", None)
        normalized.pop("to_date", None)

        return self._clean_query_params(normalized)

    def _normalize_driver_report_params(self, params: dict | None) -> dict:
        """Normalize params for driver report endpoints (no pay field, requires driverType)."""
        source = params if isinstance(params, dict) else {}
        normalized = dict(source)

        today = date.today()
        default_from = (today - timedelta(days=2)).isoformat()
        default_to = today.isoformat()

        from_date = (
            self._normalize_date_yyyy_mm_dd(source.get("fromDate"))
            or self._normalize_date_yyyy_mm_dd(source.get("from_date"))
            or default_from
        )
        to_date = (
            self._normalize_date_yyyy_mm_dd(source.get("toDate"))
            or self._normalize_date_yyyy_mm_dd(source.get("to_date"))
            or default_to
        )

        normalized["fromDate"] = from_date
        normalized["toDate"] = to_date
        # driverType is required (binding:"oneof=normalDriver")
        normalized.setdefault("driverType", "normalDriver")

        # Normalize orgId
        org_id = source.get("orgId") or source.get("org_id")
        if org_id is not None:
            try:
                normalized["orgId"] = int(org_id)
            except (TypeError, ValueError):
                logger.warning("Invalid orgId value %r — ignoring", org_id)
            normalized.pop("org_id", None)

        # Normalize eTaxStatus (accept common aliases, keep canonical API key).
        etax_status = (
            source.get("eTaxStatus")
            or source.get("etaxStatus")
            or source.get("etax_status")
            or source.get("e_tax_status")
        )
        if etax_status is not None:
            try:
                normalized["eTaxStatus"] = int(etax_status)
            except (TypeError, ValueError):
                logger.warning("Invalid eTaxStatus value %r — ignoring", etax_status)

        normalized.pop("etaxStatus", None)
        normalized.pop("etax_status", None)
        normalized.pop("e_tax_status", None)

        # Driver reports do NOT accept pay — remove if provided.
        normalized.pop("pay", None)
        normalized.pop("from_date", None)
        normalized.pop("to_date", None)

        return self._clean_query_params(normalized)

    def _get_report_data(self, path: str, params: dict | None = None) -> dict:
        """Shared GET wrapper for report endpoints (non-download APIs only)."""
        try:
            normalized_params = self._normalize_report_params(params)
            payload = self._get(path, params=normalized_params)

            # Preserve meta from PagingSuccessResponse before unwrapping.
            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}

            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data

            # Go marshals empty slices as null → data is None after unwrap.
            if data is None:
                return {"rows": [], "count": 0, "total_count": meta.get("totalCount", 0)}

            if isinstance(data, list):
                rows = data[:100]
                return {"rows": rows, "count": len(data), "total_count": meta.get("totalCount", len(data))}

            if isinstance(data, dict):
                rows = (
                    data.get("rows")
                    or data.get("list")
                    or data.get("items")
                    or data.get("data")
                )
                if isinstance(rows, list):
                    slim_rows = rows[:100]
                    extras = {
                        k: v
                        for k, v in data.items()
                        if k not in ("rows", "list", "items", "data")
                    }
                    return {"rows": slim_rows, "count": len(rows), "total_count": meta.get("totalCount", len(rows)), **extras}
                return data

            return {"raw": data}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "report endpoint %s HTTP %s — body: %s",
                path,
                exc.response.status_code,
                exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("report endpoint %s network error — %s", path, exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("report endpoint %s unexpected error — %s: %s", path, type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def _get_driver_report_data(self, path: str, params: dict | None = None) -> dict:
        """GET wrapper for driver report endpoints (uses driver-specific param normalization)."""
        try:
            normalized_params = self._normalize_driver_report_params(params)
            payload = self._get(path, params=normalized_params)

            meta = payload.get("meta", {}) if isinstance(payload, dict) else {}

            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data

            if data is None:
                return {"rows": [], "count": 0, "total_count": meta.get("totalCount", 0)}

            if isinstance(data, list):
                rows = data[:100]
                return {"rows": rows, "count": len(data), "total_count": meta.get("totalCount", len(data))}

            if isinstance(data, dict):
                rows = (
                    data.get("rows")
                    or data.get("list")
                    or data.get("items")
                    or data.get("data")
                )
                if isinstance(rows, list):
                    slim_rows = rows[:100]
                    extras = {
                        k: v
                        for k, v in data.items()
                        if k not in ("rows", "list", "items", "data")
                    }
                    return {"rows": slim_rows, "count": len(rows), "total_count": meta.get("totalCount", len(rows)), **extras}
                return data

            return {"raw": data}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "driver report endpoint %s HTTP %s — body: %s",
                path,
                exc.response.status_code,
                exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("driver report endpoint %s network error — %s", path, exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("driver report endpoint %s unexpected error — %s: %s", path, type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    # ------------------------------------------------------------------
    # Public API methods (read-only)
    # ------------------------------------------------------------------

    def get_order_detail(self, order_id: str) -> dict:
        """
        Fetch B2C detail for a single order.

        Endpoint: GET /api/v1/orders/{orderId}
        Response shape: { "success": true, "data": {...}, "errors": null }
        """
        normalized_id = (order_id or "").strip()
        upper_id = normalized_id.upper()
        # Guard against organization names or free-text accidentally routed here.
        if not (
            (upper_id.startswith("ORD-") and any(ch.isdigit() for ch in upper_id[4:]))
            or (normalized_id.isdigit() and len(normalized_id) >= 5)
        ):
            return {
                "error": "REQUEST_INVALID",
                "detail": "order_id format is invalid. Use numeric id or ORD-* format.",
                "order_id": order_id,
            }

        try:
            payload = self._get(f"/orders/{normalized_id}")
            if isinstance(payload, dict):
                if not payload.get("success", True):
                    logger.error("get_order: success=false for order_id=%s — %s", normalized_id, payload.get("errors"))
                    return {"error": "ORDER_SERVICE_ERROR", "detail": payload.get("errors")}
                data = payload.get("data") or payload
                if isinstance(data, dict):
                    return self._slim_order_detail(data)
                if isinstance(data, list) and data:
                    first = data[0]
                    if isinstance(first, dict):
                        return self._slim_order_detail(first)
                    if isinstance(first, list) and first:
                        return self._slim_order_detail(first[0])
                return {"error": "ORDER_NOT_FOUND", "order_id": order_id}
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

    def get_orders(self, status: str) -> dict:
        """
        List orders filtered by status code.

        Endpoint: GET /api/v1/orders?status={status}
        Response shape: { "success": true, "data": [...] or {...}, "errors": null }
        Valid status values: pending, active, completed, incompleted,
        cancelled, return, waitingForPayment.
        Returns {"orders": [...], "count": N}.
        """
        try:
            payload = self._get("/orders", params={"status": status, "pageSize": 10})
            if isinstance(payload, dict):
                if not payload.get("success", True):
                    logger.error("search_orders: success=false status=%s — %s", status, payload.get("errors"))
                    return {"error": "ORDER_SERVICE_ERROR", "detail": payload.get("errors")}
                data = payload.get("data", payload)
            else:
                data = payload
            if isinstance(data, list):
                orders = data[:10]
                return {"orders": [self._slim_order(o) for o in orders], "count": len(data)}
            # data is a wrapper dict e.g. {"orders": [...], "total": N}
            orders = (data.get("data") or data.get("orders") or [])[:10]
            count = data.get("total") or data.get("count") or len(orders)
            return {"orders": [self._slim_order(o) for o in orders], "count": count}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "search_orders HTTP %s for status=%s — body: %s",
                exc.response.status_code, status, exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("search_orders network error status=%s — %s", status, exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "search_orders unexpected error status=%s — %s: %s",
                status, type(exc).__name__, exc,
            )
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_delayed_orders(self) -> dict:
        """
        List all orders currently in Transit (in-transit / delayed).

        Endpoint: GET /api/v1/orders?status=Transit
        Response shape: { "success": true, "data": [...] or {...}, "errors": null }
        Returns {"delayed_orders": [...], "count": N}.
        """
        try:
            payload = self._get("/orders", params={"status": "Transit", "pageSize": 10})
            if isinstance(payload, dict):
                if not payload.get("success", True):
                    logger.error("get_delayed_orders: success=false — %s", payload.get("errors"))
                    return {"error": "ORDER_SERVICE_ERROR", "detail": payload.get("errors")}
                data = payload.get("data", payload)
            else:
                data = payload
            raw = data if isinstance(data, list) else (data.get("data") or data.get("orders") or [])
            orders = raw[:10]
            return {"delayed_orders": [self._slim_order(o) for o in orders], "count": len(raw)}
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

    def get_order_payment_status(self, order_id: str) -> dict:
        """
        Check payment/branchPay status of an order.

        Endpoint: GET /api/v1/orders/{orderId}/status
        Used for orders where branchPay is active (statusCd=7).
        """
        try:
            payload = self._get(f"/orders/{order_id}/status")
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "ORDER_NOT_FOUND", "order_id": order_id}
            logger.error(
                "get_order_payment_status HTTP %s for order_id=%s — body: %s",
                exc.response.status_code, order_id, exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_order_payment_status network error for order_id=%s — %s", order_id, exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "get_order_payment_status unexpected error for order_id=%s — %s: %s",
                order_id, type(exc).__name__, exc,
            )
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_order_cancel_fee(self, order_id: str) -> dict:
        """
        Get the cancellation fee preview for an order.

        Endpoint: GET /api/v1/orders/{orderId}/cancel-fee
        """
        try:
            payload = self._get(f"/orders/{order_id}/cancel-fee")
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "ORDER_NOT_FOUND", "order_id": order_id}
            logger.error(
                "get_order_cancel_fee HTTP %s for order_id=%s — body: %s",
                exc.response.status_code, order_id, exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_order_cancel_fee network error for order_id=%s — %s", order_id, exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "get_order_cancel_fee unexpected error for order_id=%s — %s: %s",
                order_id, type(exc).__name__, exc,
            )
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_order_statistics(self) -> dict:
        """
        Get per-user Web2/customer order statistics dashboard.

        Endpoint: GET /api/v1/orders/statistics
        Scope: current authenticated user only (not full-system).
        """
        try:
            payload = self._get("/orders/statistics")
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "get_order_statistics HTTP %s — body: %s",
                exc.response.status_code, exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_order_statistics network error — %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_order_statistics unexpected error — %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_statement_of_use_summary(self, params: dict | None = None) -> dict:
        """GET /api/v1/report/statement-of-use/summary (full-system customer report)."""
        return self._get_report_data("/report/statement-of-use/summary", params=params)

    def get_statement_of_use_detail(self, params: dict | None = None) -> dict:
        """GET /api/v1/report/statement-of-use/detail (full-system customer report)."""
        return self._get_report_data("/report/statement-of-use/detail", params=params)

    def get_statement_of_use_driver_summary(self, params: dict | None = None) -> dict:
        """GET /api/v1/report/statement-of-use-driver/summary (driver report — no pay param, requires driverType)."""
        return self._get_driver_report_data("/report/statement-of-use-driver/summary", params=params)

    def get_statement_of_use_driver_detail(self, params: dict | None = None) -> dict:
        """GET /api/v1/report/statement-of-use-driver/detail (driver report — no pay param, requires driverType)."""
        return self._get_driver_report_data("/report/statement-of-use-driver/detail", params=params)

    def get_b2b_tracking_service_detail(self, params: dict | None = None) -> dict:
        """GET /api/v1/report/b2b-tracking-service/detail."""
        return self._get_report_data("/report/b2b-tracking-service/detail", params=params)

    def get_coupons(self) -> dict:
        """
        Get the list of coupons for the current user.

        Endpoint: GET /api/v1/coupons
        """
        try:
            payload = self._get("/coupons")
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            if isinstance(data, list):
                return {"coupons": data, "count": len(data)}
            coupons = data.get("data") or data.get("coupons") or [] if isinstance(data, dict) else []
            return {"coupons": coupons, "count": len(coupons)}
        except httpx.HTTPStatusError as exc:
            logger.error(
                "get_coupons HTTP %s — body: %s",
                exc.response.status_code, exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_coupons network error — %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("get_coupons unexpected error — %s: %s", type(exc).__name__, exc)
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_order_route(self, order_id: str) -> dict:
        """
        Get the delivery route (waypoints) for an authenticated user's order.

        Endpoint: GET /api/v1/orders/{orderId}/route
        Response includes waypoint details, sequence, status, and coordinates.
        """
        try:
            payload = self._get(f"/orders/{order_id}/route")
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            # If route is a list of waypoints, slim them; if it's a dict, return as-is
            if isinstance(data, list):
                waypoints = self._slim_waypoints(data, limit=20)
                return {"waypoints": waypoints, "count": len(waypoints)}
            if isinstance(data, dict):
                # Check if data contains waypoints under a key
                waypoints = data.get("waypoints") or data.get("route") or []
                if isinstance(waypoints, list):
                    slimmed = self._slim_waypoints(waypoints, limit=20)
                    return {"waypoints": slimmed, "count": len(slimmed), **{k: v for k, v in data.items() if k not in ("waypoints", "route")}}
                return data
            return data
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "ORDER_NOT_FOUND", "order_id": order_id}
            logger.error(
                "get_order_route HTTP %s for order_id=%s — body: %s",
                exc.response.status_code, order_id, exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_order_route network error for order_id=%s — %s", order_id, exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "get_order_route unexpected error for order_id=%s — %s: %s",
                order_id, type(exc).__name__, exc,
            )
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_order_shipping_records(self, keyword: str = "") -> dict:
        """
        Get user's recent delivery addresses (shipping records) for reorder suggestions.

        Endpoint: GET /api/v1/orders/shipping-records?keyword=...
        Used by Web2 to suggest past destinations when user creates new order.
        """
        try:
            params = {"keyword": keyword} if keyword else {}
            payload = self._get("/orders/shipping-records", params=params)
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            # Response is typically a list of waypoint records or a dict with list inside
            if isinstance(data, list):
                records = self._slim_waypoints(data, limit=15)
                return {"records": records, "count": len(records)}
            if isinstance(data, dict):
                records = data.get("data") or data.get("records") or data.get("waypoints") or []
                if isinstance(records, list):
                    slimmed = self._slim_waypoints(records, limit=15)
                    return {"records": slimmed, "count": len(slimmed), **{k: v for k, v in data.items() if k not in ("data", "records", "waypoints")}}
                return data
            return data
        except httpx.HTTPStatusError as exc:
            logger.error(
                "get_order_shipping_records HTTP %s — body: %s",
                exc.response.status_code, exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_order_shipping_records network error — %s", exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "get_order_shipping_records unexpected error — %s: %s", type(exc).__name__, exc
            )
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    def get_order_reorder_info(self, order_id: str) -> dict:
        """
        Get order data to pre-populate reorder form when customer wants to reorder.

        Endpoint: GET /api/v1/orders/{orderId}/reorder
        Returns: origin order + pre-filled data for new order creation.
        """
        try:
            payload = self._get(f"/orders/{order_id}/reorder")
            data = self._unwrap_success_payload(payload)
            if isinstance(data, dict) and data.get("error"):
                return data
            # Slim the reorder payload to keep it compact
            if isinstance(data, dict):
                return {
                    "orderId": data.get("orderId") or data.get("id"),
                    "fromPlace": self._slim_place(data.get("fromPlace")),
                    "toPlace": self._slim_place(data.get("toPlace")),
                    "fromAddress": data.get("fromAddress"),
                    "toAddress": data.get("toAddress"),
                    "goods": self._slim_goods_infos(data.get("goodsInfos", [])),
                    "appointmentAt": data.get("appointmentAt"),
                    "notes": data.get("notes") or data.get("remark"),
                    "vehicle": self._slim_vehicle(data.get("vehicle")),
                    # Also include any extra fields that might be reorder defaults
                    "prefilledData": {k: v for k, v in data.items() if k not in (
                        "orderId", "id", "fromPlace", "toPlace", "fromAddress", "toAddress",
                        "goodsInfos", "appointmentAt", "notes", "remark", "vehicle"
                    )}
                }
            return data
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {"error": "ORDER_NOT_FOUND", "order_id": order_id}
            logger.error(
                "get_order_reorder_info HTTP %s for order_id=%s — body: %s",
                exc.response.status_code, order_id, exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("get_order_reorder_info network error for order_id=%s — %s", order_id, exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "get_order_reorder_info unexpected error for order_id=%s — %s: %s",
                order_id, type(exc).__name__, exc,
            )
            return {"error": "UNEXPECTED_ERROR", "detail": str(exc)}

    # ------------------------------------------------------------------
    # Price estimation API methods (read-only business operations)
    # ------------------------------------------------------------------

    def estimate_guest(self, payload: dict) -> dict:
        """POST /api/v1/guest/estimate."""
        return self._call_price_endpoint("/guest/estimate", payload=payload, requires_auth=False)

    def estimate_authenticated(self, payload: dict) -> dict:
        """POST /api/v1/estimate."""
        return self._call_price_endpoint("/estimate", payload=payload, requires_auth=True)

    def check_driver_price(self, payload: dict) -> dict:
        """POST /api/v1/guest/check-price-driver."""
        return self._call_price_endpoint(
            "/guest/check-price-driver",
            payload=payload,
            requires_auth=False,
        )

    def calc_guest_order_price(self, order_id: str, user_id: int | None = None) -> dict:
        """POST /api/v1/guest/orders/calc-price/{orderId}."""
        if user_id is None:
            return {
                "error": "REQUEST_INVALID",
                "detail": "user_id is required for /guest/orders/calc-price/{orderId}",
            }
        return self._call_price_endpoint(
            f"/guest/orders/calc-price/{order_id}",
            payload={"userID": user_id, "userId": user_id},
            requires_auth=False,
        )

    def estimate_guest_home_moving(self, payload: dict) -> dict:
        """POST /api/v1/guest/home-moving/estimate."""
        return self._call_price_endpoint(
            "/guest/home-moving/estimate",
            payload=payload,
            requires_auth=False,
        )

    def _call_price_endpoint(self, path: str, payload: dict, requires_auth: bool) -> dict:
        """Shared wrapper for estimate/check-price endpoints."""
        try:
            raw = self._post(path, json_body=payload, requires_auth=requires_auth)
            data = self._unwrap_success_payload(raw)
            if isinstance(data, dict) and data.get("error"):
                return data
            return self._slim_price_result(data)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "price endpoint %s HTTP %s — body: %s",
                path,
                exc.response.status_code,
                exc.response.text,
            )
            return {"error": "ORDER_SERVICE_ERROR", "detail": str(exc)}
        except httpx.RequestError as exc:
            logger.error("price endpoint %s network error — %s", path, exc)
            return {"error": "NETWORK_ERROR", "detail": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error("price endpoint %s unexpected error — %s: %s", path, type(exc).__name__, exc)
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
