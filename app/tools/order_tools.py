"""Order tools exposed to the Gemini AI model.

Each function is a thin wrapper around OrderServiceClient so that:
- The AI layer receives clean, serialisable dicts.
- No raw exceptions ever reach the orchestrator.
- Tool signatures and docstrings are preserved so Gemini's auto-generated
  JSON schemas remain unchanged.
"""

from app.services.order_service_client import get_order_client


def get_order(order_id: str) -> dict:
    """
    Get the details of a specific order by its ID.

    Args:
        order_id: The unique order identifier (e.g. 'ORD-001').

    Returns:
        A dictionary with order details, or an error message if not found.
    """
    return get_order_client().get_order(order_id)


def search_orders(status: str) -> dict:
    """
    Search for all orders that have a specific status.

    Args:
        status: The order status code to filter by. Use the exact values
                from the Order Service: 'Pending', 'Active', 'Completed',
                'Incompleted', 'Cancelled', 'Return', 'WaitingForPayment',
                'Transit'.

    Returns:
        A dictionary with a list of matching orders and the total count.
    """
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
    """
    Estimate pre-order price for guest flow.

    Args:
        payload: Request body for POST /guest/estimate.

    Returns:
        A compact dictionary with basePrice and breakdown.
    """
    return get_order_client().estimate_guest(payload)


def estimate_authenticated_price(payload: dict) -> dict:
    """
    Estimate pre-order price for authenticated flow.

    Args:
        payload: Request body for POST /estimate.

    Returns:
        A compact dictionary with basePrice and breakdown.
    """
    return get_order_client().estimate_authenticated(payload)


def check_driver_price(payload: dict) -> dict:
    """
    Estimate price for a specific driver.

    Args:
        payload: Request body for POST /guest/check-price-driver.

    Returns:
        A compact dictionary with basePrice, breakdown, and optional driver info.
    """
    return get_order_client().check_driver_price(payload)


def calc_guest_order_price(order_id: str, user_id: int | None = None) -> dict:
    """
    Re-calculate price for an existing order in guest flow.

    Args:
        order_id: Existing order id in path param.
        user_id: User id required by backend for validation.

    Returns:
        A compact dictionary with basePrice and breakdown.
    """
    return get_order_client().calc_guest_order_price(order_id, user_id)


def estimate_guest_home_moving_price(payload: dict) -> dict:
    """
    Estimate home-moving price in guest flow.

    Args:
        payload: Request body for POST /guest/home-moving/estimate.

    Returns:
        A compact dictionary with basePrice and breakdown.
    """
    return get_order_client().estimate_guest_home_moving(payload)
