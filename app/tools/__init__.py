from app.tools.analytics_tools import get_order_summary, get_revenue_today
from app.tools.driver_tools import get_driver, list_active_drivers
from app.tools.order_tools import get_delayed_orders, get_order, search_orders

# All tool functions exposed to the AI model.
# Gemini auto-generates JSON schemas from each function's type hints and docstring.
ALL_TOOL_FUNCTIONS: list = [
    get_order,
    search_orders,
    get_delayed_orders,
    get_driver,
    list_active_drivers,
    get_order_summary,
    get_revenue_today,
]

# Maps function name → callable so the orchestrator can execute tool calls.
TOOL_REGISTRY: dict = {fn.__name__: fn for fn in ALL_TOOL_FUNCTIONS}
