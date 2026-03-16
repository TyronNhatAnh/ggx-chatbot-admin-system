# AdminCancelOrders

## Endpoint
`POST /api/v1/orders/admin-cancel`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `AdminCancelOrders`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	var req model.AdminCancelOrdersRequest
	err := validation.CheckValidateHTTP(c, &req)
	if err != nil {
		return
	}

	userId, err := httpcommon.GetUserId(c)
	if err != nil || userId != constants.Anonymous.UserID {
		c.JSON(http.StatusForbidden, httpcommon.NewErrorResponse(httpcommon.PerMissionDenied, httpcommon.RequestInvalid, "accessToken"))
		return
	}
	token := httpcommon.GetAuthToken(c)

	reponse, errorCommon := h.orderNewService.AdminCancelOrders(c.Request.Context(), req, token)
	if errorCommon.Error != nil {
		httpcommon.ExposeError(c, errorCommon)
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(reponse))
}
```

## Detected Service Calls

- `orderNewService.AdminCancelOrders()`
