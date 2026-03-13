# ---------------------------------------------------------------------------
# Analytics tools
#
# These functions return pre-computed summary metrics.  In a real project
# they would query a data warehouse, a metrics store, or run aggregations
# against a live database.
# ---------------------------------------------------------------------------


def get_order_summary() -> dict:
    """
    Get a high-level summary of all orders grouped by their current status.

    Returns:
        A dictionary with order counts per status and the total order count.
    """
    # Values mirror the MOCK_ORDERS dataset in order_tools.py.
    return {
        "total_orders": 5,
        "by_status": {
            "delivered": 1,
            "pending": 1,
            "cancelled": 1,
            "in_transit": 1,
            "delayed": 1,
        },
    }


def get_revenue_today() -> dict:
    """
    Get the total revenue generated from orders delivered today.

    Returns:
        A dictionary containing today's revenue total, currency, and the
        number of orders that were delivered.
    """
    # Mock value — represents revenue from the single delivered order (ORD-001).
    return {
        "revenue_today": 1299.99,
        "currency": "USD",
        "delivered_orders_count": 1,
    }
