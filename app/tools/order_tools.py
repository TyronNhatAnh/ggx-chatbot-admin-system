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
