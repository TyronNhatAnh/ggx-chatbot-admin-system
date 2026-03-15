# ReOrder

## Endpoint
`GET /api/v1/orders/:orderId/reorder`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `ReOrder`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	orderRequestId, err := strconv.ParseInt(c.Param("orderId"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.OrderIdIsInvalid, httpcommon.RequestInvalid, "orderId"))
		return
	}

	order, errCommon := h.orderNewService.ReOrder(c.Request.Context(), orderRequestId)
	if errCommon.Error != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(errCommon.Error.Error(), httpcommon.RequestInvalid, errCommon.Field))
		return

	}
	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(order))
}
```

## Detected Service Calls

- `orderNewService.ReOrder()`
- `Request.Context()`
- `Error.Error()`
