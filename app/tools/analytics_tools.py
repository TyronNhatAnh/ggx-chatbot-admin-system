# ---------------------------------------------------------------------------
# Analytics tools
#
# These functions return pre-computed summary metrics.  In a real project
# they would query a data warehouse, a metrics store, or run aggregations
# against a live database.
# ---------------------------------------------------------------------------


def get_order_summary() -> dict:
    """Return aggregate order counts grouped by status (mock data)."""
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
    """Return total revenue from today's delivered orders (mock data)."""
    # Mock value — represents revenue from the single delivered order (ORD-001).
    return {
        "revenue_today": 1299.99,
        "currency": "USD",
        "delivered_orders_count": 1,
    }
