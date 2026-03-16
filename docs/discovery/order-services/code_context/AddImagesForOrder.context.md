# AddImagesForOrder

## Endpoint
`POST /api/v1/orders/:orderId/images`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `AddImagesForOrder`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	var request model.AddImagesRequest

	userId, err := httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, "UserID"))
		return
	}
	request.UserID = uint64(userId)

	request.OrderRequestID, err = strconv.ParseInt(c.Param("orderId"), 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, "orderId"))
	}

	err = validation.CheckValidateHTTP(c, &request)
	if err != nil {
		return
	}
	logger.Info("AddImagesForOrder", zap.Any("AddImagesRequest: ", request))

	response, errorReponse := h.orderService.AddImagesForOrder.Handle(c.Request.Context(), request)
	if errorReponse.Message != "" {
		if errorReponse.Field != "" {
			c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(errorReponse.Message, errorReponse.Code, errorReponse.Field))
			return
		}
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(errorReponse.Message, httpcommon.SystemError, ""))
		return
	}

	logger.Info("AddImagesForOrder", zap.Any("Response: ", response))
	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(response))
}
```

## Detected Service Calls

- `AddImagesForOrder.Handle()`
