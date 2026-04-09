"""Order tools exposed to the Gemini AI model.

Each function is a thin wrapper around OrderServiceClient so that:
- The AI layer receives clean, serialisable dicts.
- No raw exceptions ever reach the orchestrator.
- Tool signatures and docstrings are preserved so Gemini's auto-generated
  JSON schemas remain unchanged.
"""

from app.services.order_service_client import get_order_client


def get_order_detail(order_id: str) -> dict:
    """Get full detail of a single order by ID (GET /admin/orders/{orderId}).
    Use when the user wants any detailed info about a specific order: status, driver, vehicle, price breakdown,
    waypoints, goods, payment, owner, flags, notes, or any other order field.
    Prefer this over get_orders_admin_panel when only one specific order ID is known.

    Args:
        order_id: The order ID to retrieve.
    """
    return get_order_client().get_order_detail(order_id)


def get_order_payment_status(order_id: str) -> dict:
    """Check payment/branchPay status of an order (GET /orders/:orderId/status). Use when user asks about payment status."""
    return get_order_client().get_order_payment_status(order_id)


def get_order_cancel_fee(order_id: str, user_id: int | None = None) -> dict:
    """Get cancellation fee preview for an order (GET /orders/:orderId/cancel-fee).
    user_id: the customer's userId from orderOwner.userId (required by the API — call get_order_detail first if not known).
    """
    return get_order_client().get_order_cancel_fee(order_id, user_id=user_id)


def get_orders_admin_panel(
    keyword: str | None = None,
    status_cd: list[int] | None = None,
    order_type: list[str] | None = None,
    pay_cd: list[int] | None = None,
    group_type_cd: list[int] | None = None,
    appointment_from: str | None = None,
    appointment_to: str | None = None,
    organization_ids: list[int] | None = None,
    not_organization_ids: list[int] | None = None,
    branch_ids: list[int] | None = None,
    not_branch_ids: list[int] | None = None,
    user_id: int | None = None,
    driver_id: int | None = None,
    order_request_id: int | None = None,
    request_vehicle_pool_id: int | None = None,
    delivery_vehicle_pool_id: int | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict:
    """Get ALL orders from the admin panel (GET /admin/orders). Returns orders across ALL statuses.
    Use this for general order listing and searching across all statuses.

    Args:
        keyword: Free-text search across order ID, vehicle, customer name, driver name,
                 contact info, pickup and destination locations.
        status_cd: Filter by status codes (e.g. [1] for Pending, [4] for InTransit, [3] for Completed,
                   [5] for Cancelled, [2] for Active). Multiple values = OR. Omit for all statuses.
        order_type: Filter by order type strings (e.g. ["Quick", "Delivery", "HomeMoving"]).
        pay_cd: Filter by payment method codes.
        group_type_cd: Filter by group type codes (0=Normal, 1=Parent, 2=ChildOrder1, 3=ChildOrder2).
        appointment_from: Appointment date range start (YYYY-MM-DD).
        appointment_to: Appointment date range end (YYYY-MM-DD).
        organization_ids: Include only these organization IDs (IN condition). Use for org-specific queries.
        not_organization_ids: Exclude these organization IDs (NOT IN condition).
        branch_ids: Include only these branch IDs (IN condition).
        not_branch_ids: Exclude these branch IDs (NOT IN condition).
        user_id: Filter by customer user ID.
        driver_id: Filter by assigned driver ID.
        order_request_id: Look up a specific order by its internal integer ID.
        request_vehicle_pool_id: Filter by vehicle pool requested in the order.
        delivery_vehicle_pool_id: Filter by driver's registered vehicle pool.
        sort_by: Field to sort by. Allowed: "id", "createdAt", "appointmentAt", "completedAt",
                 "cancelledAt", "pickupAt", "statusCd", "payCD", "orderType", "groupTypeCD", "quantity".
        sort_order: Sort direction: "asc" or "desc".
        limit: Max number of results (system-enforced max: 5).
        offset: Pagination offset (0-based page index).
    """
    return get_order_client().get_orders_admin_panel(
        params={
            "keyword": keyword,
            "status_cd": status_cd,
            "order_type": order_type,
            "pay_cd": pay_cd,
            "group_type_cd": group_type_cd,
            "appointment_from": appointment_from,
            "appointment_to": appointment_to,
            "organization_ids": organization_ids,
            "not_organization_ids": not_organization_ids,
            "branch_ids": branch_ids,
            "not_branch_ids": not_branch_ids,
            "user_id": user_id,
            "driver_id": driver_id,
            "order_request_id": order_request_id,
            "request_vehicle_pool_id": request_vehicle_pool_id,
            "delivery_vehicle_pool_id": delivery_vehicle_pool_id,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "limit": limit,
            "offset": offset,
        }
    )



def submit_order(payload: dict) -> dict:
    """Submit a new order on behalf of an admin (POST /admin/orders/submit).
    THIS IS THE ONLY WRITE ACTION PERMITTED. Only call after the admin has explicitly confirmed
    the order details. Never call speculatively or without a confirmed approval in the same turn.

    Args:
        payload: Full order creation body as required by POST /admin/orders/submit.
    """
    return get_order_client().submit_order(payload)


def get_order_history(
    order_id: str,
    page_size: int = 20,
    page_index: int = 1,
    sort_order: str = "desc",
) -> dict:
    """Get the full change history of an order — before/after values for each update to order details, user info, or price.
    Use when the user asks about order changes, update history, who changed what, or price/user modifications on a specific order.

    Endpoint: GET /orders/{orderId}/history

    Args:
        order_id: The order ID to retrieve history for.
        page_size: Number of history entries per page (default: 20).
        page_index: Page number, 1-based (default: 1).
        sort_order: Sort direction: "asc" or "desc" (default: "desc" — newest first).
    """
    return get_order_client().get_order_history(
        order_id, page_size=page_size, page_index=page_index, sort_order=sort_order
    )


def get_customer_statement_summary(
    from_date: str,
    to_date: str,
    pay: list[str],
    org_id: int | None = None,
    businessline_cd: int | None = None,
    branch: list[str] | None = None,
) -> dict:
    """Customer Statement-of-Use summary: one row per org/business-line with aggregated order counts and fares.
    Endpoint: GET /admin/report/statement-of-use/summary

    Returns StatementOfUseDataSummary rows plus meta.additionalData totals (totalCustomerFare, totalOrderCount).
    Summary returns ALL matching rows without pagination.

    Args:
        from_date: Start date (YYYY-MM-DD). Required.
        to_date: End date (YYYY-MM-DD). Required.
        pay: Payment method filter. Required. Valid values: "Credit" (후불), "Cash" (현금).
             Pass ["Credit", "Cash"] to include all payments.
        org_id: Filter by organization ID.
        businessline_cd: Filter by business line code.
        branch: Filter by branch codes (list of strings).
    """
    return get_order_client().get_customer_statement_summary(
        from_date=from_date,
        to_date=to_date,
        pay=pay,
        org_id=org_id,
        businessline_cd=businessline_cd,
        branch=branch,
    )


def get_customer_statement_detail(
    from_date: str,
    to_date: str,
    pay: list[str],
    org_id: int | None = None,
    businessline_cd: int | None = None,
    page_size: int = 10,
    page_index: int = 1,
) -> dict:
    """Customer Statement-of-Use detail: one row per order with full fare breakdown and driver info.
    Endpoint: GET /admin/report/statement-of-use/detail

    Returns StatementOfUseDataDetail rows. Paginated — use page_size + page_index.
    Nullable fields serialize as {"Float64": <val>, "Valid": <bool>} — treat as null when Valid=false.

    Args:
        from_date: Start date (YYYY-MM-DD). Required.
        to_date: End date (YYYY-MM-DD). Required.
        pay: Payment method filter. Required. Valid values: "Credit" (후불), "Cash" (현금).
             Pass ["Credit", "Cash"] to include all payments.
        org_id: Filter by organization ID.
        businessline_cd: Filter by business line code.
        page_size: Rows per page (default 10).
        page_index: Page number, 1-based (default 1).
    """
    return get_order_client().get_customer_statement_detail(
        from_date=from_date,
        to_date=to_date,
        pay=pay,
        org_id=org_id,
        businessline_cd=businessline_cd,
        page_size=page_size,
        page_index=page_index,
    )


def get_driver_statement_summary(
    from_date: str,
    to_date: str,
    driver_type: str = "normalDriver",
    org_id: int | None = None,
    driver_id: int | None = None,
    driver_org: int | None = None,
    tax_player_cd: list[int] | None = None,
    e_tax_status: list[str] | None = None,
    is_revised: bool | None = None,
) -> dict:
    """Driver Statement-of-Use summary: one row per driver with aggregated settlement data for the period.
    Endpoint: GET /admin/report/statement-of-use-driver/summary

    Returns DriverDataSummary rows plus meta.additionalData.totalDriverCount.
    Summary returns ALL matching rows without pagination.
    Note: residentRegistrationNumber and phoneNumber are masked in API responses.

    Args:
        from_date: Start date (YYYY-MM-DD). Required.
        to_date: End date (YYYY-MM-DD). Required.
        driver_type: Must be "normalDriver" (the only supported value). Required.
        org_id: Filter by customer organization ID.
        driver_id: Filter by specific driver user ID.
        driver_org: Filter by driver's organization ID.
        tax_player_cd: Filter by tax player type codes (list of ints).
        e_tax_status: Filter by e-tax status values (list of strings).
        is_revised: Filter revised records only.
    """
    return get_order_client().get_driver_statement_summary(
        from_date=from_date,
        to_date=to_date,
        driver_type=driver_type,
        org_id=org_id,
        driver_id=driver_id,
        driver_org=driver_org,
        tax_player_cd=tax_player_cd,
        e_tax_status=e_tax_status,
        is_revised=is_revised,
    )


def get_driver_statement_detail(
    from_date: str,
    to_date: str,
    driver_type: str = "normalDriver",
    org_id: int | None = None,
    driver_id: int | None = None,
    driver_org: int | None = None,
    tax_player_cd: list[int] | None = None,
    e_tax_status: list[str] | None = None,
    is_revised: bool | None = None,
    page_size: int = 10,
    page_index: int = 1,
) -> dict:
    """Driver Statement-of-Use detail: one row per order per driver with full financial breakdown.
    Endpoint: GET /admin/report/statement-of-use-driver/detail

    Superset of driver summary fields plus order-level info and e-tax fields. Paginated.
    Note: The incentive field has JSON key "CustomerFare" (capital C) — known naming inconsistency.

    Args:
        from_date: Start date (YYYY-MM-DD). Required.
        to_date: End date (YYYY-MM-DD). Required.
        driver_type: Must be "normalDriver" (the only supported value). Required.
        org_id: Filter by customer organization ID.
        driver_id: Filter by specific driver user ID.
        driver_org: Filter by driver's organization ID.
        tax_player_cd: Filter by tax player type codes (list of ints).
        e_tax_status: Filter by e-tax status values (list of strings).
        is_revised: Filter revised records only.
        page_size: Rows per page (default 10).
        page_index: Page number, 1-based (default 1).
    """
    return get_order_client().get_driver_statement_detail(
        from_date=from_date,
        to_date=to_date,
        driver_type=driver_type,
        org_id=org_id,
        driver_id=driver_id,
        driver_org=driver_org,
        tax_player_cd=tax_player_cd,
        e_tax_status=e_tax_status,
        is_revised=is_revised,
        page_size=page_size,
        page_index=page_index,
    )



