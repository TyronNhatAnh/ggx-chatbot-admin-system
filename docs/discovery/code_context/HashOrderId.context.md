# HashOrderId

## Endpoint
`GET /api/v1/guest/etax/hash-order/:id`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `HashOrderId`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	param := c.Param("id")
	orderRequestID, err := strconv.ParseInt(param, 10, 64)
	if err != nil {
		logger.ErrorCtx(c.Request.Context(), "Invalid E-Tax order ID", zap.Error(err), zap.String("id", param))
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.RequestInvalid, httpcommon.OrderETaxInvalid, "id"))
		return
	}

	// decrypt order request ID
	orderRequestIDHashed, err := stringutils.EncodeHashID(h.cfg.HashID.EtaxOrderSalt, orderRequestID)
	if err != nil {
		logger.Error("EncodeHashID orderId", zap.Error(err))
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.RequestInvalid, httpcommon.OrderETaxInvalid, "id"))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(orderRequestIDHashed))
}
```

## Detected Service Calls

- `Request.Context()`
