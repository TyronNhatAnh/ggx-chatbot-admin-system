# DownloadDriverSummary

## Endpoint
`GET /api/v1/report/statement-of-use-driver/summary/download`

## Handler
- **Variable:** `reportNewHandler`
- **Receiver type:** `ReportHandler`
- **Method:** `DownloadDriverSummary`

## File
`internal/api/http/v1/report_handler.go`

## Handler Code
```go
{
	var request model.DriverSummaryRequest
	err := validation.GetQueryParamsHTTP(c, &request)
	if err != nil {
		return
	}

	resp, err := h.statementOfUseService.GetDriverSummary(c.Request.Context(), request)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
		return
	}

	url, err := h.statementOfUseService.ExportToExcelDriverSummary(c.Request.Context(), resp, request)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse([]string{url}))
}
```

## Detected Service Calls

- `statementOfUseService.GetDriverSummary()`
- `Request.Context()`
- `statementOfUseService.ExportToExcelDriverSummary()`
