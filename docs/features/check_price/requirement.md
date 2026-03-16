# Feature Requirement Document: Check Price and Order Lifecycle

## Overview
The `check_price` feature set encompasses the entire lifecycle of price estimation, order creation, and post-order management (including tax invoicing and status tracking) for both standard delivery and home-moving services.

## Detailed Use Cases

### UC-1: Price Estimation (Guest/User)
- **Actor**: Guest or Authenticated User
- **Trigger**: User enters delivery details to see a price quote.
- **Validation**: System checks the `OrderType`. If `HOME_MOVING`, it routes to the specialized home-moving estimator.
- **Happy Path**:
    1. User provides waypoints and vehicle type.
    2. Frontend calls `POST /guest/estimate` (or `/guest/home-moving/estimate`).
    3. Backend returns a `ResultOrder` containing the calculated price.
- **Evidence**: `src/lib/apis/order.ts` -> `OrderAPIs.estimate`.

### UC-2: Order Submission
- **Actor**: Authenticated User
- **Trigger**: User confirms the order after reviewing the estimate.
- **Validation**: Phone numbers in the payload are converted to strings via `convertPhoneListToString`.
- **Happy Path**:
    1. User submits order details.
    2. System routes to `POST /orders` or `POST /home-moving/orders` based on type.
    3. Order is created and ID is returned.
- **Evidence**: `src/lib/apis/order.ts` -> `OrderAPIs.createOrder`.

### UC-3: Coupon Application
- **Actor**: Authenticated User
- **Trigger**: User applies a discount code.
- **Happy Path**:
    1. User registers a coupon via `POST /coupons/register-user`.
    2. User fetches applicable coupons via `GET /coupons` filtered by `orderType` and `pay` (PaymentType).
- **Evidence**: `internal/api/http/v1/routes.go` -> `couponNewHandler`.

### UC-4: E-Tax Invoice Processing
- **Actor**: Guest User
- **Trigger**: User requests a tax invoice for a completed order.
- **Happy Path**:
    1. User verifies business registration number via `GET /guest/etax/verify_biz_registration_number/:biz_registration_number`.
    2. User retrieves order data via `GET /guest/etax/get-order/:id`.
    3. User issues invoice via `POST /guest/etax/issue_tax_invoice`.
- **Evidence**: `src/lib/apis/order.ts` -> `OrderAPIs.createIssueTaxInvoice`.

### UC-5: Order Tracking and History
- **Actor**: User / Guest
- **Trigger**: User wants to see the status or route of an order.
- **Happy Path**:
    1. User fetches order details via `GET /orders/:orderId`.
    2. User fetches route waypoints via `GET /orders/:orderId/route` (or `guest/orders/route/:orderId` for guests).
- **Evidence**: `internal/api/http/v1/routes.go` -> `orderHandler.GetWayPointRouteByOrderID`.

## Business Rules
- **Environment Restriction**: The endpoint `GET /guest/etax/hash-order/:id` is strictly prohibited in production environments (`environ != "prod"`).
- **B2B Integration**: Specific endpoints exist for B2B partners (e.g., DHL) to retrieve order details without standard user authentication via `GET /guest/orders/:orgId/:orderId`.
- **Tip Submission**: Users can add tips to orders post-creation via `POST /orders/:orderId/submit-tip`.

## Error Handling
- **Error Code**: `UNKNOWN` (The provided source code does not explicitly define error code constants, though handlers like `orderNewHandler` are responsible for returning appropriate HTTP statuses).
- **Validation**: Frontend performs parameter transformation (e.g., phone list conversion) before submission to ensure backend compatibility.