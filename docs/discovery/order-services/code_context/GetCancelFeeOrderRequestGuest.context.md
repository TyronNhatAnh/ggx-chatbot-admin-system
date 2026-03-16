# GetCancelFeeOrderRequestGuest

## Endpoint
`POST /api/v1/guest/orders/cancel-fee/:orderId`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `GetCancelFeeOrderRequestGuest`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	var req model.CancelFeeOrderRequest
	err := validation.CheckValidateHTTP(c, &req)
	if err != nil {
		return
	}

	h.handleGetCancelFeeOrderRequest(c, req)
}
```

## Detected Service Calls

_No service calls detected._
