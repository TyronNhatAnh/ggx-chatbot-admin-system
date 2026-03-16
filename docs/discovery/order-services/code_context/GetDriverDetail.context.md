# GetDriverDetail

## Endpoint
`GET /api/v1/report/statement-of-use-driver/detail`

## Handler
- **Variable:** `reportNewHandler`
- **Receiver type:** `ReportHandler`
- **Method:** `GetDriverDetail`

## File
`internal/api/http/v1/report_handler.go`

## Handler Code
```go
{
	var (
		paging    = httpcommon.ParseParams(c)
		params    = model.DriverSummaryRequest{}
		pageIndex = httpcommon.GetCurrentPage(c)
	)

	err := validation.GetQueryParamsHTTP(c, &params)
	if err != nil {
		return
	}
	params.Limit = paging.Limit
	params.Offset = paging.Offset

	resp, err := h.statementOfUseService.GetDriverDetail(c.Request.Context(), params)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewPagingSuccessResponse(resp.Detail, int(resp.AdditionalData.TotalCount), resp.AdditionalData, paging.Limit, pageIndex))
}
```

## Detected Service Calls

- `statementOfUseService.GetDriverDetail()`
