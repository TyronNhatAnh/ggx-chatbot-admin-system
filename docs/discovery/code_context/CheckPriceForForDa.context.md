# CheckPriceForForDa

## Endpoint
`POST /api/v1/guest/check-price-driver`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `CheckPriceForForDa`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	var req checkPriceDriver.CheckPriceDriverRequest

	// check and binding req
	err := validation.CheckValidateHTTP(c, &req)
	if err != nil {
		return
	}
	logger.InfoCtx(c.Request.Context(), "Info Price For Da", zap.Any("Request: ", req))

	driverInfo, err := h.baseService.DriverClient.GetDriverById(c, &driverGrpc.GetDriverByIdsRequest{
		Id: req.DriverId,
	})
	if err != nil || driverInfo.UserId == 0 {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(constants.DriverInvalid, httpcommon.RequestInvalid, "driverId"))
		return
	}

	order, field, err := h.orderService.CheckDriverPriceHandler.Handle(c.Request.Context(), &req, driverInfo)
	if err != nil {
		if field != "" {
			c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, field))
			return
		}
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}
	logger.InfoCtx(c.Request.Context(), "Info Price For Da", zap.Any("Respondse: ", order))
	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(order))
}
```

## Detected Service Calls

- `Request.Context()`
- `DriverClient.GetDriverById()`
- `CheckDriverPriceHandler.Handle()`
