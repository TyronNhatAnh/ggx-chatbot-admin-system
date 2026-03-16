# HomeMovingAdminGetOrderRequests

## Endpoint
`GET /api/v1/home-moving/admin/orders`

## Handler
- **Variable:** `homeMovingHandler`
- **Receiver type:** `HomeMovingHandler`
- **Method:** `HomeMovingAdminGetOrderRequests`

## File
`internal/api/http/v1/home_moving_handler.go`

## Handler Code
```go
{
	var (
		req    model.HomeMovingAdminGetOrdersRequest
		paging = httpcommon.ParseParams(c)
	)

	// check and binding req
	err := validation.GetQueryParamsHTTP(c, &req)
	if err != nil {
		return
	}

	req.Limit = paging.Limit
	req.Offset = paging.Offset

	res, totalRows, errorCommon := h.homeMovingService.HomeMovingAdminGetOrderRequests(c, req)
	if errorCommon.Error != nil {
		httpcommon.ExposeError(c, errorCommon)
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewPagingSuccessResponse(res, int(totalRows), nil, req.Limit))
}
```

## Detected Service Calls

- `homeMovingService.HomeMovingAdminGetOrderRequests()`
