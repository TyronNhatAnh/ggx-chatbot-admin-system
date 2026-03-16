# GetOrders

## Endpoint
`GET /api/v1/orders`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `GetOrders`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	var (
		req    model.GetOrderRequestsReq
		paging = httpcommon.ParseParams(c)
	)

	pageIndex := httpcommon.GetCurrentPage(c)

	// check and binding req
	err := validation.GetQueryParamsHTTP(c, &req)
	if err != nil {
		return
	}

	req.Limit = paging.Limit
	req.Offset = paging.Offset

	userId, err := httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}

	req.UserId = uint64(userId)

	resp, totalRows, respErr := h.orderService.GetOrdersHandler.Handle(c.Request.Context(), req)
	if respErr.Error != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(respErr.Error.Error(), httpcommon.SystemError, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewPagingSuccessResponse(resp.Orders, int(totalRows), resp.Statistics, paging.Limit, pageIndex, constants.IsKeepAdditionalData))
}
```

## Detected Service Calls

- `GetOrdersHandler.Handle()`
