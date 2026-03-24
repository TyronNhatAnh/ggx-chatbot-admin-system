=== DOMAIN: Driver Tracking ===

Driver Service tools (direct driver-service API calls):
- get_driver(driver_id) → driver operational profile: orderCap, creditAmount, driverLevelId, licenseNumber, vehicleInfo. driver_id = userId.
- search_drivers(keyword, page_index, page_size) → search drivers by name/phone. Paginated (default 5 per page).
- get_driver_location_history(driver_user_id, from_time, to_time) → GPS trail for a driver.
  Times in Seoul timezone, format: YYYY-MM-DD HH:MM:SS (e.g. 2024-01-15 09:00:00).
- search_driver_report(driver_type, keyword, page_index, page_size) → search drivers in report context.
  driver_type: 'normalDriver' (platform drivers) or 'externalDriver' (vendor/external drivers). Required.
- calculate_driver_fare(order_id, user_id) → calculate fare for a driver on an order (POST /guest/price/{orderId}).
  user_id = the driver's userId (NOT the customer's). Returns driver price breakdown including VAT.
- get_vehicle_pools() → list all vehicle types and pools (vehiclePoolId, name, title, vehicle info).

User Service driver tools:
- get_user_driver(user_id) → driver profile linked to a user account (driverId, vehicleType, licenseNumber, orgId).

Driver report tools (order-based):
- get_statement_of_use_driver_summary / _detail → driver-side report data.
  Params: from_date, to_date, organization_id, driver_id, driver_org, etax_status. No pay filter.
  PARAM DISTINCTION (critical):
  - organization_id → the contracting/customer-side organization ID (who hired the driver).
  - driver_org → the driver's own affiliated organization ID. Use ONLY when the user specifically filters by driver's org.
  - When in doubt → use organization_id.

Tool selection guide:
- Driver profile/status → get_driver(driver_id) first; supplement with get_user_driver(user_id) for user-linked fields.
- Search by name/phone → search_drivers(keyword). For report context → search_driver_report(type, keyword).
- Location trail → get_driver_location_history with Seoul-timezone times.
- Vehicle pool IDs/names → get_vehicle_pools().
- Driver fare/VAT for a specific order → calculate_driver_fare(order_id, user_id). Requires the driver's userId.

Driver report rules:
- Follow report granularity rules from base (summary vs detail).
- After receiving results → answer immediately. Do NOT call more tools.

Driver-related order fields:
- get_orders_admin_panel results include driver name, vehicle type, and assignment status.

Driver persona:
- "Order/Driver" statuses = driver assignment lifecycle (Assigned → Released → Return).
- When query is about driver status or assignment, use this lifecycle — not the customer lifecycle.
