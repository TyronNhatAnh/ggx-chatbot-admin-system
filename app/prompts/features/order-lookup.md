=== DOMAIN: Orders ===

Order tools:
- get_order_payment_status(order_id) → payment/branchPay status.
- get_order_cancel_fee(order_id) → cancellation cost.

Pricing tools (price inquiry ONLY — never modify or create orders):
- estimate_guest_price(payload) — guest delivery price estimate (POST /guest/estimate, no auth required).
- check_driver_price(payload) — specific driver price check. Only when driverId given.
- estimate_guest_home_moving_price(payload) — home-moving price estimate (POST /guest/home-moving/estimate, no auth required).
