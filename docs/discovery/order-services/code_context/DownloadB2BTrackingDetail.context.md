# DownloadB2BTrackingDetail

## Endpoint
`GET /api/v1/report/b2b-tracking-service/detail/download`

## Handler
- **Variable:** `reportNewHandler`
- **Receiver type:** `ReportHandler`
- **Method:** `DownloadB2BTrackingDetail`

## File
`internal/api/http/v1/report_handler.go`

## Handler Code
```go
{
	var (
		params = model.B2BTrackingDetailRequest{}
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

	params.OrgID = int(orgId)

	resp, err := h.b2bTrackingService.GetDetail(c.Request.Context(), params)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
		return
	}

	url, err := h.b2bTrackingService.ExportToExcelDetail(c.Request.Context(), resp)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse([]string{url}))
}
```

## Detected Service Calls

- `b2bTrackingService.GetDetail()`
- `b2bTrackingService.ExportToExcelDetail()`
