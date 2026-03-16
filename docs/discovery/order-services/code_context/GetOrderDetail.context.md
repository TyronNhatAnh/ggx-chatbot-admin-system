# GetOrderDetail

## Endpoint
`GET /api/v1/orders/:orderId/admin`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `GetOrderDetail`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	_, err := httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}

	param := c.Param("orderId")
	orderId, err := strconv.ParseInt(param, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, "id"))
		return
	}
	detail, err := h.orderService.GetOrderDetailHandler.Handler(c.Request.Context(), orderId)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}
	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(detail))
}
```

## Detected Service Calls

- `GetOrderDetailHandler.Handler()`
