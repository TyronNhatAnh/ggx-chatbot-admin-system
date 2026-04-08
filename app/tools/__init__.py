from app.tools.driver_tools import (
    calculate_driver_fare,
    get_driver,
    get_vehicle_pools,
    search_drivers,
)
from app.tools.common_tools import (
    get_addresses,
    get_vehicle_prices,
    search_api_address_details,
    search_api_addresses,
)
from app.tools.docs_tools import (
    # get_handler_context,  # s16 — temporarily disabled
    list_available_docs,
    # search_endpoints,  # s16 — temporarily disabled
)
from app.tools.knowledge_tools import (
    explain_status,
    # find_api_consumers,  # s18 — temporarily disabled
    # get_knowledge_stats,  # s18 — temporarily disabled
    lookup_enum,
    # search_codebase,  # s17 — temporarily disabled
    # traverse_graph,  # s18 — temporarily disabled
)
from app.tools.order_tools import (
    get_order_cancel_fee,
    get_order_detail,
    get_order_history,
    get_order_payment_status,
    get_orders_admin_panel,
    submit_order,
)
from app.tools.user_tools import (
    get_accessible_menu_tree,
    get_admin_permissions,
    list_admin_departments,
    list_admin_menus,
    list_admin_roles,
    search_branches,
    search_organizations,
    search_users,
    verify_biz_registration_number,
)

# All tool functions exposed to the AI model.
# Gemini auto-generates JSON schemas from each function's type hints and docstring.
ALL_TOOL_FUNCTIONS: list = [
    get_order_detail,
    get_order_payment_status,
    get_order_cancel_fee,
    get_order_history,
    get_orders_admin_panel,
    submit_order,
    # user tools — read-only user-service queries
    search_users,
    search_branches,
    search_organizations,
    list_admin_roles,
    list_admin_departments,
    list_admin_menus,
    get_admin_permissions,
    get_accessible_menu_tree,
    verify_biz_registration_number,
    # common tools — read-only common-service queries
    get_vehicle_prices,
    get_addresses,
    search_api_addresses,
    search_api_address_details,
    # driver tools — read-only driver-service queries
    get_driver,
    search_drivers,
    calculate_driver_fare,
    get_vehicle_pools,
    # docs tools — two-tier knowledge (endpoint search → handler source code)
    list_available_docs,
    # search_endpoints,  # s16 — temporarily disabled
    # get_handler_context,  # s16 — temporarily disabled
    # knowledge tools — indexed codebase knowledge (enums, search)
    lookup_enum,
    explain_status,
    # search_codebase,  # s17 — temporarily disabled
    # graph traversal tools — cross-service flow tracing
    # traverse_graph,  # s18 — temporarily disabled
    # find_api_consumers,  # s18 — temporarily disabled
    # get_knowledge_stats,  # s18 — temporarily disabled
]


def _validate_unique_tool_names(tool_functions: list) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for tool_fn in tool_functions:
        if tool_fn.__name__ in seen:
            duplicates.add(tool_fn.__name__)
        seen.add(tool_fn.__name__)

    if duplicates:
        duplicate_names = ", ".join(sorted(duplicates))
        raise ValueError(f"Duplicate tool function names found: {duplicate_names}")


_validate_unique_tool_names(ALL_TOOL_FUNCTIONS)


# Maps function name → callable so the orchestrator can execute tool calls.
TOOL_REGISTRY: dict = {fn.__name__: fn for fn in ALL_TOOL_FUNCTIONS}

# Per-feature tool subsets for Flash model session scoping.
# When a feature_key is detected, the orchestrator passes only the listed names via
# ToolConfig.allowed_function_names — restricting model choice without extra LLM calls.
# Pro model (knowledge-code) is scoped at factory creation via _PRO_TOOLS.
FLASH_TOOL_SETS: dict[str, frozenset[str]] = {
    "order-lookup": frozenset({
        "get_order_detail", "get_order_payment_status", "get_order_cancel_fee",
        "get_order_history", "get_orders_admin_panel",
        "submit_order",
        # supporting lookups for order cross-references
        "search_users", "search_organizations",
        # driver fare breakdown (order-lookup.md: driver price perspective)
        "calculate_driver_fare",
        # enum/status code lookups
        "lookup_enum", "explain_status",
    }),
    "driver-tracking": frozenset({
        "get_driver", "search_drivers", "calculate_driver_fare", "get_vehicle_pools",
        "get_vehicle_prices",
        "get_order_detail",  # needed for driver-order cross-reference
        "get_orders_admin_panel",  # needed to list orders by driver_id
    }),
    "user-admin": frozenset({
        "search_users",
        "search_branches",
        "search_organizations", "list_admin_roles", "list_admin_departments",
        "list_admin_menus", "get_admin_permissions", "get_accessible_menu_tree",
        "verify_biz_registration_number",
        # user-admin.md: last-login flow — resolve userId from order owner field
        "get_order_detail",
    }),
    "common-data": frozenset({
        "get_vehicle_prices",
        "get_addresses", "search_api_addresses", "search_api_address_details",
        # enum/status code lookups
        "lookup_enum", "explain_status",
    }),
    "email-dispatch": frozenset({
        # order read + submit
        "get_order_detail", "get_order_history", "get_orders_admin_panel",
        "submit_order",
        # user / org lookup (Step A)
        "search_users",
        "search_organizations",
        # address geocoding (Step B)
        "search_api_address_details", "search_api_addresses",
        # vehicle pool ID resolution (Step C)
        "get_vehicle_pools",
    }),
    "knowledge-code": frozenset({
        # org lookup
        "search_organizations",
        # knowledge tools
        "lookup_enum", "explain_status",
        # "search_codebase",  # s17 — temporarily disabled
        # "traverse_graph", "find_api_consumers", "get_knowledge_stats",  # s18 — temporarily disabled
        # docs tools
        "list_available_docs",
        # "search_endpoints",  # s16 — temporarily disabled
        # "get_handler_context",  # s16 — temporarily disabled
    }),
}
