"""Order tools exposed to the Gemini AI model.

Each function is a thin wrapper around OrderServiceClient so that:
- The AI layer receives clean, serialisable dicts.
- No raw exceptions ever reach the orchestrator.
- Tool signatures and docstrings are preserved so Gemini's auto-generated
  JSON schemas remain unchanged.
"""

from app.services.order_service_client import get_order_client


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
    """Get per-user order statistics dashboard (GET /orders/statistics). Not an admin aggregate."""
    return get_order_client().get_order_statistics()


def get_coupons() -> dict:
    """Get the list of coupons for the current user (GET /coupons)."""
    return get_order_client().get_coupons()


def estimate_guest_home_moving_price(payload: dict) -> dict:
    """Estimate home-moving price for a guest. payload: POST /guest/home-moving/estimate body."""
    return get_order_client().estimate_guest_home_moving(payload)
