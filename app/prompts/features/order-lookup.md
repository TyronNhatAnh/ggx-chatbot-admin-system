=== DOMAIN: Orders ===

Order list tool (ALL statuses — admin panel view):
- get_orders_admin_panel(...) → GET /admin/orders. Returns orders in ANY status (pending, in-transit, completed, cancelled, etc.).
  Use for: "list orders", "find orders by keyword/phone/driver/org", "orders today", order search by date range.
  Key filters: keyword, status_cd, order_type, pay_cd, appointment_from/to, created_from/to, organization_id, branch_id, user_id, driver_id, phone_number, order_request_id, external_order_id, limit, offset, sort_by, sort_order.
  DO NOT use for revenue/financial aggregations — use report tools for that.

Report tools (completed/cancelled orders — financial aggregation):
- get_statement_of_use_summary/detail → aggregated revenue by org/period. Filters: from_date, to_date, pay, organization_id.
- get_statement_of_use_driver_summary/detail → driver-level report.
  Use report tools for: total revenue, payment breakdown, statement of use, billing reports.

Order detail tools:
- get_order_payment_status(order_id) → payment/branchPay status.
- get_order_cancel_fee(order_id) → cancellation cost.
- get_tax_invoice_states(mgt_keys) → Barobill/NTS e-tax transmission states (POST /etax/tax-invoice-states).
  Use when user asks about e-tax invoice status, NTS submission result, barobill state, or etax transmission for specific mgt keys.

Pricing tools (price inquiry ONLY — never modify or create orders):
- estimate_guest_price(payload) — guest delivery price estimate (POST /guest/estimate, no auth required).
- check_driver_price(payload) — specific driver price check. Only when driverId given.
- estimate_guest_home_moving_price(payload) — home-moving price estimate (POST /guest/home-moving/estimate, no auth required).

Tool selection rules:
- Listing/searching orders → get_orders_admin_panel
- Revenue/billing aggregation → report tools
- Single order payment check → get_order_payment_status
