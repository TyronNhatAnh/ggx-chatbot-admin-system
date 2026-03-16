# GetETaxOrder

## Endpoint
`GET /api/v1/guest/etax/get-order/:id`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `GetETaxOrder`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	param := c.Param("id")

	// decrypt order request ID
	orderRequestID, err := stringutils.DecodeHashID(h.cfg.HashID.EtaxOrderSalt, param)
	if err != nil {
		logger.Error("DecodeHashID orderId", zap.Error(err))
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.RequestInvalid, httpcommon.OrderETaxInvalid, "id"))
		return
	}

	// validate E-Tax order
	ValidateETaxOrderRes, errorCommon := h.orderNewService.ValidateETaxOrder(c.Request.Context(), orderRequestID)
	if !ValidateETaxOrderRes {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.RequestInvalid, httpcommon.OrderETaxInvalid, "id"))
		return
	}
	if errorCommon.Error != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(errorCommon.Error.Error(), httpcommon.OrderETaxInvalid, "id"))
		return
	}

	// get Order detail for E-Tax
	res, errorCommon := h.orderNewService.GetETaxOrder(c.Request.Context(), orderRequestID)
	if errorCommon.Error != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.RequestInvalid, httpcommon.OrderETaxInvalid, "id"))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(res))
}
```

## Detected Service Calls

- `orderNewService.ValidateETaxOrder()`
- `orderNewService.GetETaxOrder()`
