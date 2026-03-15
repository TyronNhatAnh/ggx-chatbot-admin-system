# GetWaypointShippingRecords

## Endpoint
`GET /api/v1/orders/shipping-records`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `GetWaypointShippingRecords`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	var (
		paging    = httpcommon.ParseParams(c)
		req       = model.WaypointShippingRecordRequest{}
		pageIndex = httpcommon.GetCurrentPage(c)
	)

	err := validation.GetQueryParamsHTTP(c, &req)
	if err != nil {
		return
	}

	req.Limit = paging.Limit
	req.Offset = paging.Offset

	userId, err := httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, "UserID"))
		return
	}
	req.UserID = userId

	resp, totalRows, respErr := h.orderService.GetWaypointShippingRecordsHandler.Handler(c.Request.Context(), req)
	if respErr != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(respErr.Error(), httpcommon.SystemError, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewPagingSuccessResponse(resp, int(totalRows), nil, paging.Limit, pageIndex))
}
```

## Detected Service Calls

- `GetWaypointShippingRecordsHandler.Handler()`
- `Request.Context()`
