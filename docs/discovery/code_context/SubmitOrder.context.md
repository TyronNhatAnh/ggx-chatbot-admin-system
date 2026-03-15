# SubmitOrder

## Endpoint
`POST /api/v1/home-moving/orders`

## Handler
- **Variable:** `homeMovingHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `SubmitOrder`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	var request model.OrderRequestInfo
	err := validation.CheckValidateHTTP(c, &request)
	if err != nil {
		return
	}
	logger.InfoCtx(c.Request.Context(), "OrderNewHandler.SubmitOrder", zap.Any("OrderRequestInfo: ", request))

	users, isError := GetUserContent(h.baseService, c)
	if isError {
		return
	}

	reqEstimate, isError := GetEstimateReqForSibmitOrder(c, request)
	if isError {
		return
	}

	if !IsSubmitOrderValid(c, &reqEstimate, request, false) {
		return
	}

	estimateData, err := h.GetPriceEstimate(c, request, users, h.orderService)
	if err != nil {
		return
	}

	if !IsPaymentOrderValid(h.baseService, c, request, users, estimateData) {
		return
	}

	order, errCommon := h.orderNewService.HandleSubmitCommonOrder(c.Request.Context(), request, users, estimateData, httpcommon.GetAuthToken(c))
	if errCommon.Error != nil {
		httpcommon.ExposeError(c, errCommon)
		return
	}
	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(order))
}
```

## Detected Service Calls

- `Request.Context()`
- `orderNewService.HandleSubmitCommonOrder()`
