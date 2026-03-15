# GetMobisOrderById

## Endpoint
`GET /api/v1/guest/mobis/orders/:externalOrderId`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `GetMobisOrderById`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	param := c.Param("externalOrderId")

	// check external order id
	orderrequestId, err := h.orderNewService.GetOrderRequestIdByExternalOrderId(c.Request.Context(), param)
	if err != nil || orderrequestId == 0 {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.ExternalOrderIdInvalid, httpcommon.RequestInvalid, "externalOrderId"))
		return
	}

	req := model.GetOrderDetailForB2cRequest{
		OrderRequestID: orderrequestId,
		GroupType:      orderconstants.OrderRequestTypeCD.GroupType.Parent,
	}
	orderDetail, err := h.orderService.GetOrderDetailB2CHandler.Handle(c.Request.Context(), req)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.ExternalOrderIdInvalid, httpcommon.RequestInvalid, "externalOrderId"))
		return
	}

	// trim external order id
	if orderDetail.ExternalOrderID.String != "" {
		orderDetail.ExternalOrderID = null.NewString(strings.TrimSpace(orderDetail.ExternalOrderID.String), true)
	}

	user, err := h.baseService.UserClient.GetUsers(c.Request.Context(), &grpc.GetUserRequest{
		Id: orderDetail.UserID,
	})
	if err != nil || !user.IsMobisUser {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.ExternalOrderIdInvalid, httpcommon.RequestInvalid, "externalOrderId"))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(orderDetail))
}
```

## Detected Service Calls

- `orderNewService.GetOrderRequestIdByExternalOrderId()`
- `Request.Context()`
- `GetOrderDetailB2CHandler.Handle()`
- `UserClient.GetUsers()`
