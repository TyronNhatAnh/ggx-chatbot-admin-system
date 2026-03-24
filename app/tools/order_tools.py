"""Order tools exposed to the Gemini AI model.

Each function is a thin wrapper around OrderServiceClient so that:
- The AI layer receives clean, serialisable dicts.
- No raw exceptions ever reach the orchestrator.
- Tool signatures and docstrings are preserved so Gemini's auto-generated
  JSON schemas remain unchanged.
"""

from app.services.order_service_client import get_order_client


def _build_report_params(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    pay: list[str] | None = None,
    organization_id: int | None = None,
    params: dict | None = None,
) -> dict:
    """Merge explicit report args with optional params dict for compatibility."""
    merged = dict(params or {})
    if from_date is not None:
        merged["from_date"] = from_date
    if to_date is not None:
        merged["to_date"] = to_date
    if pay is not None:
        merged["pay"] = pay
    if organization_id is not None:
        merged["orgId"] = organization_id
    return merged

def _build_driver_report_params(
    *,
    etax_status: int,
    from_date: str | None = None,
    to_date: str | None = None,
    organization_id: int | None = None,
    driver_id: int | None = None,
    driver_org: int | None = None,
) -> dict:
    """Build params for driver report endpoints (no pay param, supports eTaxStatus)."""
    merged: dict = {"eTaxStatus": etax_status}
    if from_date is not None:
        merged["from_date"] = from_date
    if to_date is not None:
        merged["to_date"] = to_date
    if organization_id is not None:
        merged["orgId"] = organization_id
    if driver_id is not None:
        merged["driverId"] = driver_id
    if driver_org is not None:
        merged["driverOrg"] = driver_org
    return merged


def estimate_guest_price(payload: dict) -> dict:
    """Estimate price for a new guest order. payload: POST /guest/estimate body."""
    return get_order_client().estimate_guest(payload)


def check_driver_price(payload: dict) -> dict:
    """Estimate price for a specific driver. payload must include driverId (POST /guest/check-price-driver)."""
    return get_order_client().check_driver_price(payload)


def get_order_payment_status(order_id: str) -> dict:
    """Check payment/branchPay status of an order (GET /orders/:orderId/status). Use when user asks about payment status."""
    return get_order_client().get_order_payment_status(order_id)


def get_order_cancel_fee(order_id: str) -> dict:
    """Get cancellation fee preview for an order (GET /orders/:orderId/cancel-fee)."""
    return get_order_client().get_order_cancel_fee(order_id)


def get_statement_of_use_summary(
    from_date: str | None = None,
    to_date: str | None = None,
    pay: list[str] | None = None,
    organization_id: int | None = None,
) -> dict:
    """Get customer report summary (aggregated by organization). Returns orderCount, totalRevenue, paymentBreakdown — NO per-order rows.
    Use for overview/aggregate questions. For per-order data with orderId, use get_statement_of_use_detail instead.

    Args:
        from_date: Start date (YYYY-MM-DD). Omit to use backend default (last 3 days).
        to_date: End date (YYYY-MM-DD). Omit to use backend default.
        pay: Payment types to include. Omit (None) to include ALL types automatically.
             Valid values: "cash", "credit", "card", "point", "brandpay".
             Do NOT call lookup_enum to discover these — use them directly.
        organization_id: Org system ID to filter results to a single organization.
    """
    return get_order_client().get_statement_of_use_summary(
        params=_build_report_params(from_date=from_date, to_date=to_date, pay=pay, organization_id=organization_id)
    )


def get_statement_of_use_detail(
    from_date: str | None = None,
    to_date: str | None = None,
    pay: list[str] | None = None,
    organization_id: int | None = None,
) -> dict:
    """Get customer report detail rows (per-order). Returns orderId, paymentMethod, revenue per order.
    Use when user asks for per-order breakdown, specific order IDs, or order-level payment data.
    For aggregate totals only, use get_statement_of_use_summary instead.

    Args:
        from_date: Start date (YYYY-MM-DD). Omit to use backend default (last 3 days).
        to_date: End date (YYYY-MM-DD). Omit to use backend default.
        pay: Payment types to include. Omit (None) to include ALL types automatically.
             Valid values: "cash", "credit", "card", "point", "brandpay".
             Do NOT call lookup_enum to discover these — use them directly.
        organization_id: Org system ID to filter results to a single organization.
    """
    return get_order_client().get_statement_of_use_detail(
        params=_build_report_params(from_date=from_date, to_date=to_date, pay=pay, organization_id=organization_id)
    )


def get_statement_of_use_driver_summary(
    etax_status: int,
    from_date: str | None = None,
    to_date: str | None = None,
    organization_id: int | None = None,
    driver_id: int | None = None,
    driver_org: int | None = None,
) -> dict:
    """Get driver report summary. No pay filter (driver reports don't support it).

    Args:
        etax_status: Required. E-Tax status code filter (sent as eTaxStatus).
            1 SUBMITED, 2 TEMPORARILY_SAVED, 3 CANCELED, 4 NOT_SENT,
            5 TRANSMITTING, 6 TRANSMISSION_SUCCEED, 7 TRANSMISSION_FAILED,
            8 SUBMITED_FAILED, 9 REVISED, 10 REVISED_FAILED,
            11 REVISED_SIX, 12 REVISED_SEVEN, 13 REVISED_OTHER,
            14 ALL, 15 NOT_REVISED. Use 14 to include all statuses.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        organization_id: Org system ID to filter results.
        driver_id: Filter by specific driver ID.
        driver_org: Filter by driver's organization ID.
    """
    return get_order_client().get_statement_of_use_driver_summary(
        params=_build_driver_report_params(
            etax_status=etax_status,
            from_date=from_date, to_date=to_date,
            organization_id=organization_id, driver_id=driver_id, driver_org=driver_org,
        )
    )


def get_statement_of_use_driver_detail(
    etax_status: int,
    from_date: str | None = None,
    to_date: str | None = None,
    organization_id: int | None = None,
    driver_id: int | None = None,
    driver_org: int | None = None,
) -> dict:
    """Get driver report detail rows (per-order). No pay filter (driver reports don't support it).

    Args:
        etax_status: Required. E-Tax status code filter (sent as eTaxStatus).
            1 SUBMITED, 2 TEMPORARILY_SAVED, 3 CANCELED, 4 NOT_SENT,
            5 TRANSMITTING, 6 TRANSMISSION_SUCCEED, 7 TRANSMISSION_FAILED,
            8 SUBMITED_FAILED, 9 REVISED, 10 REVISED_FAILED,
            11 REVISED_SIX, 12 REVISED_SEVEN, 13 REVISED_OTHER,
            14 ALL, 15 NOT_REVISED. Use 14 to include all statuses.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        organization_id: Org system ID to filter results.
        driver_id: Filter by specific driver ID.
        driver_org: Filter by driver's organization ID.
    """
    return get_order_client().get_statement_of_use_driver_detail(
        params=_build_driver_report_params(
            etax_status=etax_status,
            from_date=from_date, to_date=to_date,
            organization_id=organization_id, driver_id=driver_id, driver_org=driver_org,
        )
    )


def estimate_guest_home_moving_price(payload: dict) -> dict:
    """Estimate home-moving price for a guest. payload: POST /guest/home-moving/estimate body."""
    return get_order_client().estimate_guest_home_moving(payload)


def get_orders_admin_panel(
    keyword: str | None = None,
    status_cd: list[int] | None = None,
    order_type: list[str] | None = None,
    pay_cd: list[int] | None = None,
    appointment_from: str | None = None,
    appointment_to: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    organization_id: int | None = None,
    branch_id: int | None = None,
    user_id: int | None = None,
    driver_id: int | None = None,
    phone_number: str | None = None,
    order_request_id: int | None = None,
    external_order_id: str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict:
    """Get ALL orders from the admin panel (GET /admin/orders). Returns orders across ALL statuses.
    Use this for general order listing, not for completed/cancelled reports.
    For aggregated revenue reports, use get_statement_of_use_summary/detail instead.

    Args:
        keyword: Free-text search across order fields.
        status_cd: Filter by status codes (e.g. [1] for Pending, [4] for InTransit, [5] for Completed).
                   Multiple values = OR. Omit for all statuses.
        order_type: Filter by order type strings (e.g. ["Quick", "Delivery", "HomeMoving"]).
        pay_cd: Filter by payment method codes.
        appointment_from: Appointment date range start (YYYY-MM-DD).
        appointment_to: Appointment date range end (YYYY-MM-DD).
        created_from: Order creation date range start (YYYY-MM-DD).
        created_to: Order creation date range end (YYYY-MM-DD).
        organization_id: Filter by organization (system ID).
        branch_id: Filter by branch ID.
        user_id: Filter by customer user ID.
        driver_id: Filter by assigned driver ID.
        phone_number: Filter by customer phone number.
        order_request_id: Look up a specific order by its internal integer ID.
        external_order_id: Look up by external order ID string.
        sort_by: Field to sort by (e.g. "createdAt", "appointmentAt").
        sort_order: Sort direction: "asc" or "desc".
        limit: Max number of results (system-enforced max: 5).
        offset: Pagination offset.
    """
    return get_order_client().get_orders_admin_panel(
        params={
            "keyword": keyword,
            "status_cd": status_cd,
            "order_type": order_type,
            "pay_cd": pay_cd,
            "appointment_from": appointment_from,
            "appointment_to": appointment_to,
            "created_from": created_from,
            "created_to": created_to,
            "organization_id": organization_id,
            "branch_id": branch_id,
            "user_id": user_id,
            "driver_id": driver_id,
            "phone_number": phone_number,
            "order_request_id": order_request_id,
            "external_order_id": external_order_id,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "limit": limit,
            "offset": offset,
        }
    )


def get_tax_invoice_states(mgt_keys: list[str]) -> dict:
    """Check Barobill/NTS e-tax transmission states for a list of management keys (POST /etax/tax-invoice-states).
    Use when user asks about e-tax invoice status, NTS submission result, or etax transmission.

    Args:
        mgt_keys: List of Barobill management key strings to check (e.g. ["20240101-1", "20240101-2"]).
    """
    return get_order_client().get_tax_invoice_states(mgt_keys)



