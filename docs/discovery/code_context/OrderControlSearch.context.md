# OrderControlSearch

## Endpoint
`GET /api/v1/order-control/search`

## Handler
- **Variable:** `orderControlHandler`
- **Receiver type:** `OrderControlHandler`
- **Method:** `OrderControlSearch`

## File
`internal/api/http/v1/order_control_handler.go`

## Handler Code
```go
{
	var (
		paging = httpcommon.ParseParams(c)
		params = model.ParamOrderControlSearch{}
	)

	err := validation.GetQueryParamsHTTP(c, &params)
	if err != nil {
		return
	}

	params.Limit = paging.Limit
	params.Offset = paging.Offset

	resp, totalRow, err := h.service.SearchOrderHandler.Handle(c.Request.Context(), params)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewPagingSuccessResponse(resp.Orders, int(totalRow), nil, params.Limit))
}
```

## Detected Service Calls

- `SearchOrderHandler.Handle()`
- `Request.Context()`
