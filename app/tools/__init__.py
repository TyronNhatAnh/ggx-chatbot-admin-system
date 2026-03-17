from app.tools.docs_tools import (
    get_handler_context,
    list_available_docs,
    search_endpoints,
)
from app.tools.knowledge_tools import (
    explain_status,
    find_api_consumers,
    get_knowledge_stats,
    get_struct_definition,
    lookup_enum,
    search_codebase,
    trace_full_stack,
    trace_service_flow,
    traverse_graph,
)
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
from app.tools.user_tools import (
    get_feature_flags,
    get_my_feature_flags,
    get_tos_contents,
    get_withdraw_reasons,
)

# All tool functions exposed to the AI model.
# Gemini auto-generates JSON schemas from each function's type hints and docstring.
# NOTE: get_delayed_orders is intentionally excluded — it is identical to
# get_orders(status='Transit') and its presence caused Gemini to call both.
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
    # user tools — read-only user-service queries
    get_withdraw_reasons,
    get_tos_contents,
    get_feature_flags,
    get_my_feature_flags,
    # docs tools — two-tier knowledge (endpoint search → handler source code)
    list_available_docs,
    search_endpoints,
    get_handler_context,
    # knowledge tools — indexed codebase knowledge (enums, flows, structs, search)
    lookup_enum,
    explain_status,
    trace_service_flow,
    get_struct_definition,
    search_codebase,
    # graph traversal tools — cross-service flow tracing
    traverse_graph,
    find_api_consumers,
    trace_full_stack,
    get_knowledge_stats,
]


# Maps function name → callable so the orchestrator can execute tool calls.
TOOL_REGISTRY: dict = {fn.__name__: fn for fn in ALL_TOOL_FUNCTIONS}
