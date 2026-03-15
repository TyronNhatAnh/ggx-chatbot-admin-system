# GetDriverSummary

## Endpoint
`GET /api/v1/report/statement-of-use-driver/summary`

## Handler
- **Variable:** `reportNewHandler`
- **Receiver type:** `ReportHandler`
- **Method:** `GetDriverSummary`

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

	c.JSON(http.StatusOK, httpcommon.NewPagingSuccessResponse(resp.Detail, 0, resp.AdditionalData))
}
```

## Detected Service Calls

- `statementOfUseService.GetDriverSummary()`
- `Request.Context()`
