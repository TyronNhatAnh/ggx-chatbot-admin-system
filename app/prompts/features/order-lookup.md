=== DOMAIN: Orders ===

Order tools:
- get_orders(status) → orderId, price, driverFee, fromPlace, toPlace, driver, vehicle, goods, payment summary. Call once per turn.
  Valid status: pending, active, completed, cancelled, return, waitingForPayment. Use lowercase.
- get_order_detail(order_id) → priceBreakdown, goods, payment, waypoints, userId. Only when fields missing from get_orders.
- get_order_payment_status(order_id) → payment/branchPay status.
- get_order_cancel_fee(order_id) → cancellation cost.
- get_order_route(order_id) → live route/waypoints. Prefer for tracking.
- get_order_shipping_records(keyword) → past delivery addresses.
- get_order_reorder_info(order_id) → pre-filled reorder data.
- get_coupons() → user coupon list.
- get_order_statistics() → personal stats only.
- B2B → get_b2b_tracking_service_detail(params).

Pricing tools (new orders ONLY — never for existing):
- estimate_guest_price(payload) — guest delivery.
- estimate_authenticated_price(payload) — authenticated user (primary channel).
- check_driver_price(payload) — specific driver. Only when driverId given.
- estimate_guest_home_moving_price(payload) — home-moving only.
