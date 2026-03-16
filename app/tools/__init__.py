from app.tools.analytics_tools import get_order_summary, get_revenue_today
from app.tools.order_tools import (
    check_driver_price,
    estimate_authenticated_price,
    estimate_guest_home_moving_price,
    estimate_guest_price,
    get_coupons,
    get_order_cancel_fee,
    get_order_detail,
    get_order_payment_status,
    get_order_statistics,
    get_orders,
)

# All tool functions exposed to the AI model.
# Gemini auto-generates JSON schemas from each function's type hints and docstring.
# NOTE: get_delayed_orders is intentionally excluded — it is identical to
# get_orders(status='Transit') and its presence caused Gemini to call both.
# NOTE: get_driver / list_active_drivers excluded — not yet connected to a real service
#       (raise NotImplementedError). Re-add once driver service client is implemented.
# NOTE: get_order_summary / get_revenue_today return MOCK data — excluded until real
#       analytics endpoints are available.
ALL_TOOL_FUNCTIONS: list = [
    get_order_detail,
    get_orders,
    get_order_payment_status,
    get_order_cancel_fee,
    get_order_statistics,
    get_coupons,
    estimate_guest_price,
    estimate_authenticated_price,
    check_driver_price,
    estimate_guest_home_moving_price,
]


# Maps function name → callable so the orchestrator can execute tool calls.
TOOL_REGISTRY: dict = {fn.__name__: fn for fn in ALL_TOOL_FUNCTIONS}
