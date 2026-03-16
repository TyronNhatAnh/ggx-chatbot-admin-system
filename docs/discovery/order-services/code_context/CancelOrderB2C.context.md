# CancelOrderB2C

## Endpoint
`POST /api/v1/orders/:orderId/b2c-cancel`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `CancelOrderB2C`

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

	h.cancelOrder(c, userId, false, constants.RoleB2CUserCA)
}
```

## Detected Service Calls

_No service calls detected._
