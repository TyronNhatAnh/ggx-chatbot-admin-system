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
    pay: list[str] | str | None = None,
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
    return merged


def get_order_detail(order_id: str) -> dict:
    """Fetch full B2C detail for one order by ID (GET /orders/:orderId). Use for priceBreakdown, goods, payment, waypoints."""
    return get_order_client().get_order_detail(order_id)


def get_orders(status: str) -> dict:
    """List orders by status (GET /orders). status: Pending|Active|Completed|Incompleted|Cancelled|Return|WaitingForPayment|Transit.
    Result includes orderId, price, driverFee, fromPlace, toPlace, driver — sufficient for most queries."""
    return get_order_client().get_orders(status)


def get_delayed_orders() -> dict:
    """
    Get all orders that are currently in transit (active delivery, may be delayed).

    This queries orders with statusCd=Transit from the Order Service.

    Returns:
        A dictionary with a list of in-transit orders and the total count.
    """
    return get_order_client().get_delayed_orders()


def estimate_guest_price(payload: dict) -> dict:
    """Estimate price for a new guest order. payload: POST /guest/estimate body."""
    return get_order_client().estimate_guest(payload)


def estimate_authenticated_price(payload: dict) -> dict:
    """Estimate price for an authenticated user order. payload: POST /estimate body."""
    return get_order_client().estimate_authenticated(payload)


def check_driver_price(payload: dict) -> dict:
    """Estimate price for a specific driver. payload must include driverId (POST /guest/check-price-driver)."""
    return get_order_client().check_driver_price(payload)


def get_order_payment_status(order_id: str) -> dict:
    """Check payment/branchPay status of an order (GET /orders/:orderId/status). Use when user asks about payment status."""
    return get_order_client().get_order_payment_status(order_id)


def get_order_cancel_fee(order_id: str) -> dict:
    """Get cancellation fee preview for an order (GET /orders/:orderId/cancel-fee)."""
    return get_order_client().get_order_cancel_fee(order_id)


def get_order_statistics() -> dict:
    """Get per-user Web2/customer statistics (GET /orders/statistics). Not full-system aggregate."""
    return get_order_client().get_order_statistics()


def get_statement_of_use_summary(
    from_date: str | None = None,
    to_date: str | None = None,
    pay: list[str] | str | None = None,
) -> dict:
    """Get full-system customer report summary.

    Args:
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        pay: Payment filter(s), e.g. ["cash", "credit", "card", "point", "brandpay"].
    """
    return get_order_client().get_statement_of_use_summary(
        params=_build_report_params(from_date=from_date, to_date=to_date, pay=pay)
    )


def get_statement_of_use_detail(
    from_date: str | None = None,
    to_date: str | None = None,
    pay: list[str] | str | None = None,
    params: dict | None = None,
) -> dict:
    """Get full-system customer report detail rows.

    Args:
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        pay: Payment filter(s), e.g. ["cash", "credit", "card", "point", "brandpay"].
        params: Optional passthrough query params for paging/filter extensions.
    """
    return get_order_client().get_statement_of_use_detail(
        params=_build_report_params(from_date=from_date, to_date=to_date, pay=pay, params=params)
    )


def get_statement_of_use_driver_summary(
    from_date: str | None = None,
    to_date: str | None = None,
    pay: list[str] | str | None = None,
) -> dict:
    """Get full-system driver report summary.

    Args:
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        pay: Payment filter(s), e.g. ["cash", "credit", "card", "point", "brandpay"].
    """
    return get_order_client().get_statement_of_use_driver_summary(
        params=_build_report_params(from_date=from_date, to_date=to_date, pay=pay)
    )


def get_statement_of_use_driver_detail(
    from_date: str | None = None,
    to_date: str | None = None,
    pay: list[str] | str | None = None,
    params: dict | None = None,
) -> dict:
    """Get full-system driver report detail rows.

    Args:
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        pay: Payment filter(s), e.g. ["cash", "credit", "card", "point", "brandpay"].
        params: Optional passthrough query params for paging/filter extensions.
    """
    return get_order_client().get_statement_of_use_driver_detail(
        params=_build_report_params(from_date=from_date, to_date=to_date, pay=pay, params=params)
    )


def get_b2b_tracking_service_detail(params: dict | None = None) -> dict:
    """Get B2B tracking service detail report (GET /report/b2b-tracking-service/detail)."""
    return get_order_client().get_b2b_tracking_service_detail(params=params)


def get_coupons() -> dict:
    """Get the list of coupons for the current user (GET /coupons)."""
    return get_order_client().get_coupons()


def estimate_guest_home_moving_price(payload: dict) -> dict:
    """Estimate home-moving price for a guest. payload: POST /guest/home-moving/estimate body."""
    return get_order_client().estimate_guest_home_moving(payload)


def get_order_route(order_id: str) -> dict:
    """Get the delivery route and waypoint details for an order (GET /orders/:orderId/route).
    Returns waypoints in sequence with status, coordinates, and timestamps. Useful for tracking delivery progress."""
    return get_order_client().get_order_route(order_id)


def get_order_shipping_records(keyword: str = "") -> dict:
    """Get user's recent delivery destinations for reorder suggestions (GET /orders/shipping-records?keyword=...).
    Returns list of past delivery addresses. Useful when customer asks about previous destinations or wants to reorder."""
    return get_order_client().get_order_shipping_records(keyword)


def get_order_reorder_info(order_id: str) -> dict:
    """Get order data to reorder same route (GET /orders/:orderId/reorder).
    Returns origin/destination, goods, and appointment info. Useful when user wants to repeat a delivery."""
    return get_order_client().get_order_reorder_info(order_id)
