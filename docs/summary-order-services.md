1. SYSTEM OVERVIEW
This service is an order management backend built with Gin for logistics/delivery operations.

From the visible code, it supports:

Order pricing and estimation
Order creation and update
Order detail retrieval for B2C, B2B, admin, and external integrations
Cancellation flows (user, external order, admin)
Tip submission and payment-status handling
Driver assignment operations from order-control APIs
HomeMoving-specific estimation and order submission
Reporting endpoints (statement-of-use and B2B tracking)
Public E-Tax operations tied to completed/returned orders
File upload URL generation (presigned/reconciliation)
It mixes authenticated and guest/public APIs, with integrations to user, driver, payment, notification, common-config, and map-related services.

2. DOMAIN ENTITIES
OrderRequestEntity
Represents the core order request record.

Important fields:

ID
ParentID
UserID
VehiclePoolID
PayCD
StatusCD
AppointmentAt
FromPlace, ToPlace
OrderType
GroupTypeCD
ExternalOrderID, PieceID
CompletedAt, CancelledAt
Relationships:

Has one OrderOwner
Has many Waypoints
Has many OrderAmount rows
Has many OrderFlag rows
Has many AppliedExtra rows
Has many OrderHist rows
May have parent/child linkage via ParentID
Order
Execution/assignment layer for an order request.

Important fields:

OrderRequestID
DriverUserID, DriverUserTypeCD
StatusCD
PickupAt, CompletedAt, ReleasedAt
External driver fields
OrderOwner
Ownership metadata for an order request.

Important fields:

OrderRequestID
OrganizationID, BranchID, UserID
Name, ContactNo, Email
TypeCD
Waypoint
Stops in an order route.

Important fields:

OrderRequestID
Arrangement
StatusCD
RequestedAt, ReachedAt
RegionID
LocationLat, LocationLon
Reason, Remark
OrderAmount
Pricing breakdown rows per order.

Important fields:

OrderRequestID
TargetCD
PriceCD
Title
Amount
Priority
OrderFlag
Feature flags applied to orders.

Important fields:

OrderRequestID
TypeCD
AppliedExtra
Applied extras/services.

Important fields:

OrderRequestID
ExtraPriceID
Quantity
WaypointID
OrderHist
Order history/audit entries with metadata snapshots.

Important fields:

OrderRequestID
TypeCD
Priority
Meta
Description
CreatorCD, CreatorUserID
CreatedAt
HomeMoving entities
Specialized goods/options/services attached to waypoints for HomeMoving orders.

3. API ENDPOINTS
GET /api/v1/test-auth
Description: Auth check endpoint.

POST /api/v1/orders
Description: Submit order.

GET /api/v1/orders/:orderId/reorder
Description: Reorder data retrieval.

POST /api/v1/orders/status
Description: Update order status.

GET /api/v1/orders/:orderId/status
Description: Check order/payment status.

POST /api/v1/b2b-orders-dhl
Description: Submit B2B DHL order.

GET /api/v1/orders
Description: List/search orders.

GET /api/v1/coupons
Description: Get user coupons.

GET /api/v1/orders/:orderId
Description: B2C order detail (Web 2.0 path).

GET /api/v1/orders/shipping-records
Description: Get waypoint shipping records.

GET /api/v1/orders/:orderId/route
Description: Get order route by order ID.

GET /api/v1/orders/:orderId/cancel-fee
Description: Get cancel fee (authenticated).

POST /api/v1/guest/orders/cancel-fee/:orderId
Description: Get cancel fee (guest).

GET /api/v1/guest/orders/route/:orderId
Description: Get order route (guest/public).

POST /api/v1/guest/orders/calc-price/:orderId
Description: Calculate order price by order ID (guest).

GET /api/v1/orders/statistics
Description: Order statistics.

GET /api/v1/order-da/:orderId
Description: Get order for DA context.

GET /api/v1/orders/:orderId/admin
Description: Admin order detail.

POST /api/v1/estimate
Description: Authenticated estimate.

GET /api/v1/order-control/search
Description: Order-control search.

PATCH /api/v1/order-control/assign-multiple
Description: Assign multiple orders to driver.

POST /api/v1/order-control/filter-set/create
Description: Create order-control filter set.

POST /api/v1/guest/home-moving/estimate
Description: HomeMoving estimate (guest).

GET /api/v1/home-moving/admin/orders
Description: HomeMoving admin order list.

POST /api/v1/home-moving/orders
Description: Submit HomeMoving order.

POST /api/v1/orders/:orderId
Description: Update order.

POST /api/v1/orders/:orderId/images
Description: Add order images.

POST /api/v1/orders/:orderId/b2c-cancel
Description: Cancel B2C order.

POST /api/v1/orders/:orderId/b2b-cancel
Description: Cancel B2B order.

POST /api/v1/orders/external/:orderId/b2c-cancel
Description: Cancel external B2C order.

POST /api/v1/orders/external/:orderId/b2b-cancel
Description: Cancel external B2B order.

POST /api/v1/orders/:orderId/submit-tip
Description: Submit tip.

POST /api/v1/file/presigned
Description: Get presigned upload URL.

POST /api/v1/file/reconciliation
Description: Get reconciliation file URL.

POST /api/v1/orders/admin-cancel
Description: Admin bulk cancel orders.

POST /api/v1/coupons/register-user
Description: Register coupon by user.

POST /api/v1/parent-orders
Description: Update parent order request.

POST /api/v1/guest/parent-orders
Description: Update parent order request (guest path).

GET /api/v1/report/statement-of-use/summary
Description: Statement-of-use summary.

GET /api/v1/report/statement-of-use/summary/download
Description: Download statement-of-use summary.

GET /api/v1/report/statement-of-use/detail
Description: Statement-of-use detail.

GET /api/v1/report/statement-of-use/detail/download
Description: Download statement-of-use detail.

GET /api/v1/report/statement-of-use-driver/summary
Description: Driver statement summary.

GET /api/v1/report/statement-of-use-driver/summary/download
Description: Download driver statement summary.

GET /api/v1/report/statement-of-use-driver/detail
Description: Driver statement detail.

GET /api/v1/report/statement-of-use-driver/detail/download
Description: Download driver statement detail.

GET /api/v1/report/b2b-tracking-service/detail
Description: B2B tracking detail.

GET /api/v1/report/b2b-tracking-service/detail/download
Description: Download B2B tracking detail.

GET /api/v1/guest/mobis/orders/:externalOrderId
Description: Get order by external order ID for Mobis integration.

GET /api/v1/guest/etax/get-order/:id
Description: Get E-Tax order data.

POST /api/v1/guest/etax/issue_tax_invoice
Description: Issue E-Tax invoice.

GET /api/v1/guest/etax/verify_biz_registration_number/:biz_registration_number
Description: Verify business registration number.

GET /api/v1/guest/etax/hash-order/:id
Description: Hash E-Tax order ID (non-prod only).

POST /api/v1/guest/estimate
Description: Guest estimate.

POST /api/v1/guest/check-tip
Description: Check tip pricing.

POST /api/v1/guest/check-price-driver
Description: Check driver-side price.

GET /api/v1/guest/check-region
Description: Region check.

GET /api/v1/guest/health/check
Description: Health check.

GET /api/v1/guest/orders/:orgId/:orderId
Description: Public DHL B2B order detail.

GET /api/v1/guest/clear-cache
Description: Clear cache (non-prod only).

GET /swagger/*any
Description: Swagger UI/docs route.

4. BUSINESS WORKFLOWS
Order lifecycle
Observed statuses: Pending, Active, Completed, Incompleted, Cancelled, Return, WaitingForPayment, Transit.

Estimate flow

Builds estimate request (default pay/vehicle in some paths).
Validates order inputs.
Calculates route/pricing and returns detailed price list.
Has separate HomeMoving estimate path and logic.
Submit order flow

Submit order writes OrderRequest, owner, waypoints, amount rows, extras/flags, and history metadata.
B2B DHL has dedicated submit path.
Parent/child order update logic exists and recalculates parent status from child statuses.
Cancellation flow
B2C cancel validation from service:

Request user must own order.
Already Cancelled is rejected.
Active/Transit is rejected as already taken.
Only Pending or WaitingForPayment are cancellable.
On success, status is updated, cancel history is appended, notifications are sent.
Admin cancel validation:

Requires BrandPay payment type.
Rejects Cancelled and Active.
Allows Pending or WaitingForPayment.
Cancels payment when needed and writes history/notifications.
Tip flow

Recomputes bonus and order amount lines.
For BrandPay, validates customer key and payment status/feature flag, then performs payment action.
Writes order history for tip operations.
Order-control assign multiple

Request requires order IDs and driver ID.
Driver must exist and be active.
Only Pending and non-deleted orders are assignable.
Produces success and error lists for batch operation.
HomeMoving flow

Guest coupon use is blocked.
Appointment must be at least roughly 1 day ahead (except specific admin/update cases).
Maps HomeMoving goods/options/services into estimate and submit flows.
E-Tax flow

Validation requires order status Completed or Return.
Then runs E-Tax-specific validation/query logic before issuing tax invoice.
5. ENUMS AND STATES
OrderRequestStatus

Pending: newly created/unassigned state
Active: in-progress/assigned state
Completed: completed order
Incompleted: not fully completed
Cancelled: canceled order
Return: return flow state
WaitingForPayment: payment-pending state
Transit: transit/in-transfer state
Payment code (PayCD)

cash
credit
card
point
brandPay
bankTranser
kakaoPay
naverPay
Order flags

Scan
Express
RoundTrip
Relay
CashOnArrival
SMS
DamagedGoods
DesignatedVehicleType
DesignatedArrival
TargetCD for price rows

All
Customer
Driver
Waypoint status

Pending
Completed
Failed
Incompleted
Creator type codes

Admin
Driver
B2B
B2C
Platform codes

Android
IOS
B2CWeb
B2BWeb
API
Trial
Admin
System
E-Tax statuses

Submitted
TemporarilySaved
Canceled
NotSent
Transmitting
TransmissionSucceed
TransmissionFailed
SubmittedFailed
Revised and revised-related states
6. TOOL CAPABILITIES
Based on current API and service logic, an AI assistant could expose:

create_order(payload)
Submits a new order.

estimate_order(payload, auth_mode)
Gets price/route estimate for authenticated or guest contexts.

get_orders(filters)
Lists orders.

get_order_detail(order_id, mode)
Fetches B2C/B2B/admin detail.

update_order(order_id, payload)
Updates an order request.

cancel_order(order_id, actor_type, external_flag)
Cancels B2C/B2B/external/admin routes with status-rule enforcement.

submit_tip(order_id, bonus, payment_info)
Adds tip and triggers payment flow when required.

check_order_status(order_id, user_id)
Checks payment/order status.

get_cancel_fee(order_id, user_context)
Returns cancellation fee preview.

assign_multiple_orders(order_ids, driver_id, assigner_id)
Batch assigns pending orders.

create_order_control_filter(payload)
Creates reusable filter set for operations.

get_order_route(order_id, guest_or_auth)
Returns route/waypoint path information.

get_shipping_records(filters)
Returns waypoint shipping records.

get_order_statistics(scope)
Returns statistics.

get_home_moving_estimate(payload)
HomeMoving-specific estimate.

submit_home_moving_order(payload)
HomeMoving-specific submit.

get_reports(report_type, format)
Statement-of-use and B2B tracking detail/summary, with download variants.

get_mobis_order(external_order_id)
Fetches order via external ID for Mobis integration.

get_etax_order(order_id)
Retrieves E-Tax-ready order info.

issue_etax_invoice(payload)
Triggers tax invoice issuance.

verify_business_registration_number(number)
Validation helper for E-Tax path.

get_presigned_upload_url(payload)
Returns upload URL.

get_reconciliation_url(payload)
Returns reconciliation file URL.

7. DATA RELATIONSHIPS
Primary relationships visible in code:

OrderRequestEntity -> OrderOwner
One order request has one owner record.

OrderRequestEntity -> Waypoint
One-to-many. Waypoints represent route stops with sequencing.

Waypoint -> Goods / HomeMovingGoods / UploadDocuments
One waypoint can include goods and associated uploaded images/documents.

OrderRequestEntity -> OrderAmount
One-to-many pricing rows, split by target (customer/driver/all) and price code.

OrderRequestEntity -> OrderFlag
One-to-many flags that modify behavior/pricing.

OrderRequestEntity -> AppliedExtra
One-to-many applied extras/services, optionally waypoint-specific.

OrderRequestEntity -> OrderHist
One-to-many immutable history entries; meta JSON stores snapshots for audits.

OrderRequestEntity -> Order
Execution/assignment records tied by OrderRequestID (driver assignment and runtime states).

OrderRequestEntity -> Parent/Child OrderRequestEntity
Parent-child linkage via ParentID and group type; parent status can be derived from child statuses.

OrderRequestEntity -> Coupon / Payment / E-Tax contexts
Coupon usage, payment status/actions, and E-Tax eligibility depend on order status and metadata.