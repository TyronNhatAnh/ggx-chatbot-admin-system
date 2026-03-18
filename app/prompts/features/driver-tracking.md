=== DOMAIN: Driver Tracking ===

Driver-specific tools:
- get_user_driver(user_id) → driver profile linked to a user account.
- get_statement_of_use_driver_summary / _detail → driver-side report data.
  Params: from_date, to_date, organization_id, driver_id, driver_org. No pay filter.

Driver-related order fields:
- get_orders results include driver name, vehicle type, and assignment status.
- get_order_route(order_id) → live route/waypoints for driver tracking.

Driver persona:
- "Order/Driver" statuses = driver assignment lifecycle (Assigned → Released → Return).
- When query is about driver status or assignment, use this lifecycle — not the customer lifecycle.
