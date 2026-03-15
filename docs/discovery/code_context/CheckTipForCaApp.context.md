# CheckTipForCaApp

## Endpoint
`POST /api/v1/guest/check-tip`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `CheckTipForCaApp`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	var req model.CheckTipRequest

	// check and binding req
	err := validation.CheckValidateHTTP(c, &req)
	if err != nil {
		return
	}
	logger.InfoCtx(c.Request.Context(), "Info CheckTip For CA", zap.Any("Request: ", req))
	req.Action = orderconstants.ActionCheckTip.CAApp

	user, err := h.baseService.UserClient.GetUsers(c, &grpc.GetUserRequest{
		Id: uint64(req.UserId),
	})
	if err != nil || user.Id == 0 {
		logger.ErrorCtx(c.Request.Context(), err.Error(), zap.Error(err))
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(constants.UserInvalid, httpcommon.RequestInvalid, "userId"))
		return
	}

	order, _, errorCommon := h.orderNewService.CheckTipForCustomer(c.Request.Context(), &req, user)
	if errorCommon.Error != nil {
		httpcommon.ExposeError(c, errorCommon)
		return
	}

	logger.InfoCtx(c.Request.Context(), "Info CheckTip For CA", zap.Any("Respondse: ", order))
	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(order))
}
```

## Detected Service Calls

- `Request.Context()`
- `UserClient.GetUsers()`
- `orderNewService.CheckTipForCustomer()`
