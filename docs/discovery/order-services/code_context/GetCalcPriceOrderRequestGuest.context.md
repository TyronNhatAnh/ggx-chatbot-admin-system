# GetCalcPriceOrderRequestGuest

## Endpoint
`POST /api/v1/guest/orders/calc-price/:orderId`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `GetCalcPriceOrderRequestGuest`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	var req model.CalcPriceOrderRequest
	err := validation.CheckValidateHTTP(c, &req)
	if err != nil {
		return
	}

	h.handleGetCalcPriceOrderRequest(c, req)
}
```

## Detected Service Calls

_No service calls detected._
