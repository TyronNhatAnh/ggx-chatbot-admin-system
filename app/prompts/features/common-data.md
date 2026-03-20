=== DOMAIN: Common Data ===

Common service tools (read-only):
- get_vehicle_prices(order_type) → vehicle price list for order type.
  order_type must be one of: HomeMoving, Quick, Delivery.
- get_common_vehicle_pools() → list vehicles and vehicle pools.
- get_services_by_vehicle_pool(order_type, vehicle_pool_id, region_id?) → services available for a vehicle pool.
- get_addresses(keyword, user_id?, page, size) → saved address search.
- search_api_addresses(keyword, page, size) → external address search results.
- search_api_address_details(keyword, jibun_address?) → detailed external address lookup.
- list_guest_ads() → currently active guest ads for CA context.
- list_home_moving_goods_categories() → home-moving goods categories.
- list_home_moving_vehicles() → home-moving vehicles/pools.

Call guidance:
- For vehicle/service eligibility questions, prefer:
  1) get_common_vehicle_pools
  2) get_services_by_vehicle_pool
  3) get_vehicle_prices
- For address lookup:
  - Start with get_addresses when user-specific/saved address context is expected.
  - Use search_api_addresses and search_api_address_details for public/external map lookup.
- Keep each turn focused: avoid mixing unrelated Common tools in one response unless user asks.

Output guidance:
- Explain results in operations language (what is available, what matches, what is missing).
- If required parameters are missing (e.g., order_type or vehicle_pool_id), ask concise follow-up questions.
