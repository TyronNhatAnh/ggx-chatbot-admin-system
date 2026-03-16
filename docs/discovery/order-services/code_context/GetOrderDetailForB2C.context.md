# GetOrderDetailForB2C

## Endpoint
`GET /api/v1/orders/:orderId`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `GetOrderDetailForB2C`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	var (
		req model.GetOrderDetailForB2cRequest
		err error
	)

	req.UserID, err = httpcommon.GetUserId(c)
	if err != nil {
		logger.Error("GetUserId by Token", zap.Error(err))
		c.JSON(http.StatusUnauthorized, httpcommon.NewErrorResponse(httpcommon.UserIsNotAuthorized, httpcommon.UserIsNotAuthorized, "accessToken"))
		return
	}

	param := c.Param("orderId")
	req.OrderRequestID, err = strconv.ParseInt(param, 10, 64)
	if err != nil {
		logger.Error("ParseInt orderId", zap.Error(err))
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.OrderIdIsInvalid, httpcommon.RequestInvalid, "orderId"))
		return
	}

	req.Token = httpcommon.GetAuthToken(c)
	resp, err := h.orderService.GetOrderDetailB2CHandler.Handle(c.Request.Context(), req)
	if err == sql.ErrNoRows {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.IsNotExist, httpcommon.RequestInvalid, "orderId"))
		return
	}

	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(resp))
}
```

## Detected Service Calls

- `GetOrderDetailB2CHandler.Handle()`
