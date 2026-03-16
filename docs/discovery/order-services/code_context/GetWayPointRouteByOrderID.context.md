# GetWayPointRouteByOrderID

## Endpoint
`GET /api/v1/orders/:orderId/route`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `GetWayPointRouteByOrderID`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	var (
		req model.GeWayPointRouteRequest
		err error
	)

	req.UserID, err = httpcommon.GetUserId(c)
	if err != nil {
		logger.Error("GetUserId by Token", zap.Error(err))
		c.JSON(http.StatusUnauthorized, httpcommon.NewErrorResponse(httpcommon.UserIsNotAuthorized, httpcommon.UserIsNotAuthorized, "accessToken"))
		return
	}

	h.handleGetRoute(c, req)
}
```

## Detected Service Calls

_No service calls detected._
