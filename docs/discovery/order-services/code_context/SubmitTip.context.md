# SubmitTip

## Endpoint
`POST /api/v1/orders/:orderId/submit-tip`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `SubmitTip`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	var req model.SubmitTipRequest
	err := validation.CheckValidateHTTP(c, &req)
	if err != nil {
		return
	}

	param := c.Param("orderId")
	req.OrderRequestId, err = strconv.ParseUint(param, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
		return
	}

	user, isError := GetUserContent(h.baseService, c)
	if isError {
		return
	}

	logger.InfoCtx(c.Request.Context(), "OrderNewHandler.SubmitTip", zap.Any("Request: ", req))
	resp, errorCommon := h.orderNewService.SubmitTip(c.Request.Context(), user, req, httpcommon.GetAuthToken(c))
	if errorCommon.Error != nil {
		httpcommon.ExposeError(c, errorCommon)
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(resp))
}
```

## Detected Service Calls

- `orderNewService.SubmitTip()`
