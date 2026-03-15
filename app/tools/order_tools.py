"""Order tools exposed to the Gemini AI model.

Each function is a thin wrapper around OrderServiceClient so that:
- The AI layer receives clean, serialisable dicts.
- No raw exceptions ever reach the orchestrator.
- Tool signatures and docstrings are preserved so Gemini's auto-generated
  JSON schemas remain unchanged.
"""

from app.services.order_service_client import get_order_client


def get_order(order_id: str) -> dict:
    """Fetch detail for one order by ID. Use when order-level fields are needed (e.g. goods, priceBreakdown, payment)."""
    return get_order_client().get_order(order_id)


def search_orders(status: str) -> dict:
    """List orders by status. status: Pending|Active|Completed|Incompleted|Cancelled|Return|WaitingForPayment|Transit.
    Result includes orderId, price, driverFee, fromPlace, toPlace, driver — sufficient for most queries."""
    return get_order_client().search_orders(status)


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
    """Estimate price for a specific driver. payload must include driverId."""
    return get_order_client().check_driver_price(payload)


def calc_guest_order_price(order_id: str, user_id: int | None = None) -> dict:
    """Re-calculate price for an existing guest order. Requires order_id and user_id."""
    return get_order_client().calc_guest_order_price(order_id, user_id)


def estimate_guest_home_moving_price(payload: dict) -> dict:
    """Estimate home-moving price for a guest. payload: POST /guest/home-moving/estimate body."""
    return get_order_client().estimate_guest_home_moving(payload)
