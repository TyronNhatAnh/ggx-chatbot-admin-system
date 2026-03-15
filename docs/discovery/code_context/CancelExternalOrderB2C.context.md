# CancelExternalOrderB2C

## Endpoint
`POST /api/v1/orders/external/:orderId/b2c-cancel`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `CancelExternalOrderB2C`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	userId, err := httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}
	h.cancelOrder(c, userId, true, constants.RoleUser)
}
```

## Detected Service Calls

_No service calls detected._
