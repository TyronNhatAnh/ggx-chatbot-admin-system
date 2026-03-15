# GetOrderDetailForB2B

## Endpoint
`GET /api/v1/guest/orders/:orgId/:orderId`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `GetOrderDetailForB2B`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	paramOrderId := c.Param("orderId")
	paramOrgId := c.Param("orgId")
	orderId, err := strconv.ParseInt(paramOrderId, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, "orderId"))
		return
	}
	orgId, err := strconv.ParseInt(paramOrgId, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, "orgId"))
		return
	}

	// Check if orgId public is valid
	err = h.orderService.GetOrderDetailB2BHandler.ValidateOrganizationWithOrderId(c.Request.Context(), orderId, orgId)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, "organizationId"))
		return
	}

	req := model.GetOrderDetailForB2cRequest{
		OrderRequestID: orderId,
		GroupType:      orderConstants.OrderRequestTypeCD.GroupType.Parent,
	}
	orderDetail, err := h.orderService.GetOrderDetailB2CHandler.Handle(c.Request.Context(), req)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.ExternalOrderIdInvalid, httpcommon.RequestInvalid, "externalOrderId"))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(orderDetail))
}
```

## Detected Service Calls

- `GetOrderDetailB2BHandler.ValidateOrganizationWithOrderId()`
- `Request.Context()`
- `GetOrderDetailB2CHandler.Handle()`
