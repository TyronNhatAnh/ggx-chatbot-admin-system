# UpdateOrderStatus

## Endpoint
`POST /api/v1/orders/status`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `UpdateOrderStatus`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	var req model.UpdateOrderStatusReq
	err := validation.CheckValidateHTTP(c, &req)
	if err != nil {
		return
	}
	logger.InfoCtx(c.Request.Context(), "UpdateOrderStatus: ", zap.Any("Request: ", req))

	h.orderNewService.UpdateOrderStatus(c.Request.Context(), req)
	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(true))
}
```

## Detected Service Calls

- `orderNewService.UpdateOrderStatus()`
