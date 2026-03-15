# UpdateParentOrderRequest

## Endpoint
`POST /api/v1/guest/parent-orders`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `UpdateParentOrderRequest`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	var req model.UpdateParentOrderRequest
	err := validation.CheckValidateHTTP(c, &req)
	if err != nil {
		return
	}

	logger.InfoCtx(c.Request.Context(), "OrderNewHandler.UpdateParentOrderRequest", zap.Any("Request: ", req))
	errorCommon := h.orderNewService.UpdateParentOrderRequest(c.Request.Context(), req)
	if errorCommon.Error != nil {
		httpcommon.ExposeError(c, errorCommon)
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse[any](true))
}
```

## Detected Service Calls

- `Request.Context()`
- `orderNewService.UpdateParentOrderRequest()`
