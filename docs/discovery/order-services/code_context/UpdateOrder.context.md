# UpdateOrder

## Endpoint
`POST /api/v1/orders/:orderId`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `UpdateOrder`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	idStr := c.Param("orderId")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}
	var req model.OrderRequestInfo
	err = validation.CheckValidateHTTP(c, &req)
	if err != nil {
		return
	}

	userId, err := httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}
	// check update coupon permission
	_, _, creator, _, err := h.checkUpdateOrderPermission(c, userId, id, req)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
		return
	}

	var reqEstimate estimate.EstimateRequest
	reqEstimate.UserID = int64(creator.Id)
	reqEstimate.OrderRequestId = id
	err = copier.Copy(&reqEstimate, req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}
	// Check is valid order info
	if !IsOrderValid(c, &reqEstimate, false) {
		return
	}

	estimateData, err := h.getPriceEstimateForUpdate(c, id, req, creator)
	if err != nil {
		return
	}

	order, err := h.orderService.UpdateOrderHandler.Handler(c.Request.Context(), uint64(id), req, creator, estimateData)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(order))
}
```

## Detected Service Calls

- `UpdateOrderHandler.Handler()`
