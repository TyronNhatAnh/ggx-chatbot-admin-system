# GetOrderById

## Endpoint
`GET /api/v1/order-da/:orderId`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `GetOrderById`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	param := c.Param("orderId")
	orderId, err := strconv.ParseInt(param, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, "id"))
		return
	}
	orderDa, err := h.orderService.GetVwOrderForDaHandler.Handle(c.Request.Context(), orderId)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}
	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(orderDa))
}
```

## Detected Service Calls

- `GetVwOrderForDaHandler.Handle()`
