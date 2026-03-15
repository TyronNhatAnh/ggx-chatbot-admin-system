# GetWayPointRouteByOrderIDGuest

## Endpoint
`GET /api/v1/guest/orders/route/:orderId`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `GetWayPointRouteByOrderIDGuest`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	var req model.GeWayPointRouteRequest
	h.handleGetRoute(c, req)
}
```

## Detected Service Calls

_No service calls detected._
