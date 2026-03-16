# GetB2BTrackingDetail

## Endpoint
`GET /api/v1/report/b2b-tracking-service/detail`

## Handler
- **Variable:** `reportNewHandler`
- **Receiver type:** `ReportHandler`
- **Method:** `GetB2BTrackingDetail`

## File
`internal/api/http/v1/report_handler.go`

## Handler Code
```go
{
	var (
		paging    = httpcommon.ParseParams(c)
		params    = model.B2BTrackingDetailRequest{}
		pageIndex = httpcommon.GetCurrentPage(c)
	)
	err := validation.GetQueryParamsHTTP(c, &params)
	if err != nil {
		return
	}

	orgId, err := httpcommon.GetOrgID(c)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}

	params.Limit = paging.Limit
	params.Offset = paging.Offset
	params.OrgID = int(orgId)

	resp, err := h.b2bTrackingService.GetDetail(c.Request.Context(), params)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
		return
	}
	c.JSON(http.StatusOK, httpcommon.NewPagingSuccessResponse(resp.Detail, int(resp.AdditionalData.TotalCount), resp.AdditionalData, paging.Limit, pageIndex, constants.IsKeepAdditionalData))
}
```

## Detected Service Calls

- `b2bTrackingService.GetDetail()`
