# Feature Requirement Document: Pre-order Price Estimation

## 1. Introduction

This document outlines the requirements for the 'check_price' feature, which enables users (both guest and authenticated) to obtain price estimates and breakdowns before placing an order. The feature supports standard delivery, home-moving, and driver-specific price checks, as well as price calculation for existing orders.

## 2. Business Goals

*   Provide transparent pricing to users, allowing them to make informed decisions.
*   Support various order types (standard, home-moving) and user contexts (guest, authenticated, driver-specific).
*   Improve user experience by offering accurate and timely price estimates.
*   Facilitate specialized pricing scenarios for specific drivers or order conditions.

## 3. Detailed Use Cases

### UC-1: Guest checks estimate before placing order

**Actor:** Guest user

**Trigger:** A guest user wants a delivery quote for a new order.

**Preconditions:**
*   Waypoints (origin and destination) are provided in the request.

**Happy Path:**
1.  The client sends an estimate request to the `POST /guest/estimate` API endpoint. (Evidence: `OrderAPIs.estimate` in `src/lib/apis/order.ts`, `EstimateGuest` in `internal/api/http/v1/order_handler.go`)
2.  The backend performs validation on the request parameters, including appointment time, waypoint addresses, and coupon eligibility. (Evidence: `validation.CheckValidateHTTP`, `IsOrderValid`, `validWaypointAddressRequest`, `validCouponRequest` in `internal/api/http/v1/order_handler.go`)
3.  The pricing service calculates the estimated price and breakdown based on the provided parameters. (Evidence: `h.orderService.EstimateHandler.Handle` called by `Estimate` in `internal/api/http/v1/order_handler.go`)
4.  A response containing the total estimated price and a detailed breakdown is returned to the client.

**Edge Cases:**
*   **Invalid waypoint address:** If a waypoint address contains special characters, the request will be rejected. (Evidence: `validWaypointAddressRequest` in `internal/api/http/v1/order_handler.go`)
*   **Invalid appointment time:** If the `appointmentAt` is too soon for the specified `order_type` (e.g., less than 15 minutes for 'Quick' order, less than 30 minutes for 'Delivery' or 'CA' platform orders), the request will be rejected. (Evidence: `IsOrderValid` in `internal/api/http/v1/order_handler.go`)
*   **Attempt to use a coupon:** Guest users (identified by `user_id = 0`) are not allowed to use coupons. The request will be rejected. (Evidence: `validCouponRequest` in `internal/api/http/v1/order_handler.go`)
*   **Attempt to use a coupon on an A2B order:** Coupons cannot be applied to A2B (fixed amount) orders. The request will be rejected. (Evidence: `validCouponRequest` in `internal/api/http/v1/order_handler.go`)
*   **Missing required fields:** Standard HTTP validation will catch missing mandatory fields.

**Business Value:** This use case is critical for attracting new users and allowing them to quickly understand potential costs, which is a key factor in conversion.

### UC-2: Authenticated user checks estimate before placing order

**Actor:** Authenticated user

**Trigger:** A logged-in user wants a delivery quote for a new order.

**Preconditions:**
*   The user is successfully authenticated and provides a valid Authorization token.
*   Waypoints (origin and destination) are provided in the request.

**Happy Path:**
1.  The client sends an estimate request to the `POST /estimate` API endpoint with an Authorization token. (Evidence: `OrderAPIs.estimate` in `src/lib/apis/order.ts`, `EstimateAuth` in `internal/api/http/v1/order_handler.go`)
2.  The backend extracts the `user_id` from the provided token. (Evidence: `httpcommon.GetUserId` called by `EstimateAuth` in `internal/api/http/v1/order_handler.go`)
3.  Request validation runs, similar to the guest flow, but allowing coupons for authenticated users (if not an A2B order). (Evidence: `validation.CheckValidateHTTP`, `IsOrderValid`, `validWaypointAddressRequest`, `validCouponRequest` in `internal/api/http/v1/order_handler.go`)
4.  The pricing service calculates the estimated price and breakdown, potentially considering user-specific factors or applying valid coupons. (Evidence: `h.orderService.EstimateHandler.Handle` called by `Estimate` in `internal/api/http/v1/order_handler.go`)
5.  A response containing the total estimated price and a detailed breakdown is returned to the client.

**Edge Cases:**
*   **Invalid or expired authentication token:** The request will fail with an authorization error. (Evidence: `httpcommon.GetUserId` in `internal/api/http/v1/order_handler.go`)
*   **Invalid waypoint address, appointment time, or A2B coupon usage:** Similar validation errors as UC-1 apply. (Evidence: `IsOrderValid`, `validWaypointAddressRequest`, `validCouponRequest` in `internal/api/http/v1/order_handler.go`)

**Business Value:** This use case enhances the experience for loyal users by providing personalized pricing and the ability to utilize coupons, fostering retention and trust.

### UC-3: Guest checks driver-specific price

**Actor:** Guest user (or an internal system acting on behalf of a guest)

**Trigger:** A user or system wants to check the price for an order specifically with a particular driver.

**Preconditions:**
*   A valid `driver_id` is provided in the request.
*   Waypoints (origin and destination) are provided.

**Happy Path:**
1.  The client sends a request to the `POST /guest/check-price-driver` API endpoint. (Evidence: `CheckPriceForForDa` in `internal/api/http/v1/order_handler.go`)
2.  The backend validates the request parameters. (Evidence: `validation.CheckValidateHTTP` in `internal/api/http/v1/order_handler.go`)
3.  The system retrieves the driver's information using the provided `driver_id` from the Driver Service. (Evidence: `h.baseService.DriverClient.GetDriverById` in `internal/api/http/v1/order_handler.go`)
4.  The pricing service calculates the estimate, taking into account the specific driver's attributes or pricing rules. (Evidence: `h.orderService.CheckDriverPriceHandler.Handle` in `internal/api/http/v1/order_handler.go`)
5.  A response containing the driver-specific price breakdown is returned.

**Edge Cases:**
*   **Invalid or non-existent `driver_id`:** The request will be rejected with a `DRIVER_INVALID` error. (Evidence: `CheckPriceForForDa` in `internal/api/http/v1/order_handler.go`)
*   **Missing required fields:** Standard HTTP validation will catch missing mandatory fields.

**Business Value:** This enables flexible pricing models for specific drivers or fleets, supporting scenarios like preferred drivers or specialized services.

### UC-4: Guest checks home-moving estimate

**Actor:** Guest user

**Trigger:** A guest user wants a price estimate for a home-moving service.

**Preconditions:**
*   Waypoints (origin and destination) are provided.
*   Home-moving specific details, such as `goods_weight`, `goods_type`, and `vehicle_type`, are provided.

**Happy Path:**
1.  The client sends a request to the `POST /guest/home-moving/estimate` API endpoint. (Evidence: Route defined in `MapRoutes` in `internal/api/http/v1/routes.go`, client call in `OrderAPIs.estimate` in `src/lib/apis/order.ts`)
2.  Validation specific to home-moving requests is performed. (Evidence: UNKNOWN - handler implementation not provided)
3.  The home-moving pricing service calculates the estimate based on the specialized parameters. (Evidence: UNKNOWN - handler implementation not provided)
4.  A response with the home-moving price breakdown is returned.

**Edge Cases:**
*   **Invalid home-moving details:** If goods or vehicle types are invalid or incompatible. (Evidence: UNKNOWN - handler implementation not provided)
*   **Missing required fields:** Standard HTTP validation will catch missing mandatory fields.

**Business Value:** This caters to a distinct market segment requiring specialized pricing for complex home-moving logistics, expanding the platform's service offerings.

### UC-5: Guest checks price for an existing order

**Actor:** Guest user

**Trigger:** A guest user wants to re-calculate or confirm the price for an already created order.

**Preconditions:**
*   A valid `orderId` is provided in the request path.

**Happy Path:**
1.  The client sends a request to the `POST /guest/orders/calc-price/:orderId` API endpoint. (Evidence: `GetCalcPriceOrderRequestGuest` in `internal/api/http/v1/order_new_handler.go`)
2.  The `orderId` is extracted from the URL path and validated to ensure it's a valid integer. (Evidence: `getOrderIdAndUser` in `internal/api/http/v1/order_new_handler.go`)
3.  The service retrieves the order details and calculates the price based on the current state of the order. (Evidence: `h.orderNewService.GetCalcPriceOrderRequest` called by `handleGetCalcPriceOrderRequest` in `internal/api/http/v1/order_new_handler.go`)
4.  A response containing the calculated price and breakdown is returned to the client.

**Edge Cases:**
*   **Invalid or non-existent `orderId`:** The request will be rejected if the `orderId` cannot be parsed or if no order is found. (Evidence: `getOrderIdAndUser` in `internal/api/http/v1/order_new_handler.go`)
*   **Internal service error:** Errors during order lookup or price calculation will result in a system error.

**Business Value:** This allows for dynamic price checks on existing orders, which can be useful for post-modification price confirmation or reconciliation, improving transparency and operational flexibility.

## 4. Business Terms

*   **`vehicle_type`**: Refers to the type of vehicle required for the order (e.g., motorcycle, van, truck). This is typically represented by `vehiclePoolId` in the backend and `vehicleTypeId` in the frontend. It directly influences the `base_price` calculation.
*   **`from_place` / `to_place`**: Represent the origin and destination locations of an order. These are part of the `waypoints` list, where `from_place` is typically the first waypoint and `to_place` is the last. They are crucial for calculating distance-based pricing.
*   **`goods_weight` / `goods_type`**: Describe the characteristics of the items being transported. `goods_weight` refers to the total weight, and `goods_type` categorizes the items (e.g., 'smallbox', 'furniture'). These attributes are found within `GoodsReq` objects nested in `WaypointReq` and are particularly relevant for home-moving or specialized delivery services, affecting `surcharge` and `base_price`.
*   **`surcharge`**: An additional fee applied to the `base_price` due to specific conditions, such as extra services, special handling for goods, or peak hour demand. It is part of the `PriceFee` breakdown.
*   **`base_price`**: The fundamental cost of the delivery or service, calculated based on factors like distance, `vehicle_type`, and `order_type`, before any `surcharge` or discounts (e.g., coupons) are applied. In the response, this is often represented as the `total` in `CalculationPrice` or `basePrice` in frontend types.
*   **`guest vs authenticated flow`**: Differentiates between users who are not logged in (`guest` with `user_id = 0`) and those who are (`authenticated` with a specific `user_id` from a token). This distinction impacts features like coupon eligibility and access to user-specific data.
*   **`driver-specific price`**: A pricing calculation that takes into account the attributes or rates associated with a particular `driver_id`. This allows for customized pricing based on individual driver availability, vehicle, or special agreements, as seen in the `POST /guest/check-price-driver` endpoint.