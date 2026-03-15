# GetOrdersStatistics

## Endpoint
`GET /api/v1/orders/statistics`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `GetOrdersStatistics`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	userId, err := httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, "UserID"))
		return
	}

	res, err := h.orderService.GetOrderStatisticsHandler.Handle(c.Request.Context(), userId)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(res))
}
```

## Detected Service Calls

- `GetOrderStatisticsHandler.Handle()`
- `Request.Context()`
