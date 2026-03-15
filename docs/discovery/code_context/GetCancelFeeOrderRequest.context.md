# GetCancelFeeOrderRequest

## Endpoint
`GET /api/v1/orders/:orderId/cancel-fee`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `GetCancelFeeOrderRequest`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	userId, err := httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusForbidden, httpcommon.NewErrorResponse(httpcommon.PerMissionDenied, httpcommon.RequestInvalid, "accessToken"))
		return
	}

	h.handleGetCancelFeeOrderRequest(c, model.CancelFeeOrderRequest{
		UserID: userId,
	})
}
```

## Detected Service Calls

_No service calls detected._
