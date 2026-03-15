# CheckOrderStatus

## Endpoint
`GET /api/v1/orders/:orderId/status`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `CheckOrderStatus`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	var (
		userId  int64
		orderId int64
		err     error
	)
	userId, err = httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, "access_token"))
		return
	}
	param := c.Param("orderId")
	orderId, err = strconv.ParseInt(param, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, "orderId"))
		return
	}
	token := httpcommon.GetAuthToken(c)
	reponse, errorCommon := h.orderNewService.CheckOrderStatus(c.Request.Context(), model.CheckStatusPaymentRequest{
		OrderId: orderId,
		UserId:  userId,
	}, token)
	if errorCommon.Error != nil {
		httpcommon.ExposeError(c, errorCommon)
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(reponse))
}
```

## Detected Service Calls

- `orderNewService.CheckOrderStatus()`
- `Request.Context()`
