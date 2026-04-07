from app.tools.driver_tools import (
    calculate_driver_fare,
    get_driver,
    get_driver_location_history,
    get_vehicle_pools,
    search_driver_report,
    search_drivers,
)
from app.tools.common_tools import (
    get_addresses,
    get_common_vehicle_pools,
    get_services_by_vehicle_pool,
    get_vehicle_prices,
    list_guest_ads,
    list_home_moving_goods_categories,
    list_home_moving_vehicles,
    search_api_address_details,
    search_api_addresses,
)
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
    estimate_guest_home_moving_price,
    estimate_guest_price,
    get_order_cancel_fee,
    get_order_detail,
    get_order_history,
    get_order_payment_status,
    get_orders_admin_panel,
    get_statement_of_use_detail,
    get_statement_of_use_driver_detail,
    get_statement_of_use_driver_summary,
    get_statement_of_use_summary,
    get_tax_invoice_states,
    submit_order,
)
from app.tools.user_tools import (
    get_accessible_menu_tree,
    get_admin_permissions,
    get_branch_by_id,
    get_organization_by_id,
    get_user_driver,
    get_user_profile,
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
    get_tax_invoice_states,
    get_statement_of_use_summary,
    get_statement_of_use_detail,
    get_statement_of_use_driver_summary,
    get_statement_of_use_driver_detail,
    submit_order,
    estimate_guest_price,
    check_driver_price,
    estimate_guest_home_moving_price,
    # user tools — read-only user-service queries
    get_user_profile,
    search_users,
    get_user_driver,
    get_branch_by_id,
    search_branches,
    get_organization_by_id,
    search_organizations,
    list_admin_roles,
    list_admin_departments,
    list_admin_menus,
    get_admin_permissions,
    get_accessible_menu_tree,
    verify_biz_registration_number,
    # common tools — read-only common-service queries
    get_vehicle_prices,
    get_common_vehicle_pools,
    get_services_by_vehicle_pool,
    get_addresses,
    search_api_addresses,
    search_api_address_details,
    list_guest_ads,
    list_home_moving_goods_categories,
    list_home_moving_vehicles,
    # driver tools — read-only driver-service queries
    get_driver,
    search_drivers,
    get_driver_location_history,
    search_driver_report,
    calculate_driver_fare,
    get_vehicle_pools,
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
# Pro model features (report-summary, knowledge-code) are scoped at factory creation via _PRO_TOOLS.
FLASH_TOOL_SETS: dict[str, frozenset[str]] = {
    "order-lookup": frozenset({
        "get_order_detail", "get_order_payment_status", "get_order_cancel_fee",
        "get_order_history", "get_orders_admin_panel", "get_tax_invoice_states",
        "submit_order", "estimate_guest_price", "check_driver_price",
        "estimate_guest_home_moving_price",
        # supporting lookups for order cross-references
        "search_users", "get_user_profile", "search_organizations", "get_organization_by_id",
    }),
    "driver-tracking": frozenset({
        "get_driver", "search_drivers", "get_driver_location_history",
        "search_driver_report", "calculate_driver_fare", "get_vehicle_pools",
        "get_vehicle_prices",
        "get_order_detail",  # needed for driver-order cross-reference
    }),
    "user-admin": frozenset({
        "get_user_profile", "search_users", "get_user_driver",
        "get_branch_by_id", "search_branches", "get_organization_by_id",
        "search_organizations", "list_admin_roles", "list_admin_departments",
        "list_admin_menus", "get_admin_permissions", "get_accessible_menu_tree",
        "verify_biz_registration_number",
    }),
    "common-data": frozenset({
        "get_vehicle_prices", "get_common_vehicle_pools", "get_services_by_vehicle_pool",
        "get_addresses", "search_api_addresses", "search_api_address_details",
        "list_guest_ads", "list_home_moving_goods_categories", "list_home_moving_vehicles",
    }),
    "email-dispatch": frozenset({
        # order read + submit
        "get_order_detail", "get_order_history", "get_orders_admin_panel",
        "submit_order",
        # user / org lookup (Step A)
        "get_user_profile", "search_users",
        "get_organization_by_id", "search_organizations",
        # address geocoding (Step B)
        "search_api_address_details", "search_api_addresses",
        # vehicle pool ID resolution (Step C)
        "get_common_vehicle_pools",
    }),
}
