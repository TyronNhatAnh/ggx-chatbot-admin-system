# ---------------------------------------------------------------------------
# Mock order database
# In a real project, these functions would query a database or external API.
# ---------------------------------------------------------------------------

MOCK_ORDERS = {
    "ORD-001": {
        "id": "ORD-001",
        "status": "delivered",
        "item": "Laptop Pro",
        "customer": "Alice Wong",
        "total": 1299.99,
    },
    "ORD-002": {
        "id": "ORD-002",
        "status": "pending",
        "item": "Wireless Headphones",
        "customer": "Bob Tan",
        "total": 199.99,
    },
    "ORD-003": {
        "id": "ORD-003",
        "status": "cancelled",
        "item": "Mechanical Keyboard",
        "customer": "Charlie Lee",
        "total": 149.99,
    },
    "ORD-004": {
        "id": "ORD-004",
        "status": "pending",
        "item": "4K Monitor",
        "customer": "Diana Chen",
        "total": 599.99,
    },
    "ORD-005": {
        "id": "ORD-005",
        "status": "shipped",
        "item": "USB-C Hub",
        "customer": "Eve Lim",
        "total": 59.99,
    },
}


def get_order(order_id: str) -> dict:
    """
    Get the details of a specific order by its ID.

    Args:
        order_id: The unique order identifier (e.g. 'ORD-001').

    Returns:
        A dictionary with order details, or an error message if not found.
    """
    order = MOCK_ORDERS.get(order_id)
    if order:
        return order
    return {"error": f"Order '{order_id}' not found."}


def search_orders(status: str) -> list:
    """
    Search for all orders that have a specific status.

    Args:
        status: The order status to filter by. Allowed values: 'pending',
                'delivered', 'cancelled', 'shipped'.

    Returns:
        A list of orders matching the given status.
    """
    results = [
        order
        for order in MOCK_ORDERS.values()
        if order["status"].lower() == status.lower()
    ]
    if not results:
        return [{"message": f"No orders found with status '{status}'."}]
    return results
