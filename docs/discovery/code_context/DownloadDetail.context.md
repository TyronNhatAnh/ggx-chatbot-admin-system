# DownloadDetail

## Endpoint
`GET /api/v1/report/statement-of-use/detail/download`

## Handler
- **Variable:** `reportNewHandler`
- **Receiver type:** `ReportHandler`
- **Method:** `DownloadDetail`

## File
`internal/api/http/v1/report_handler.go`

## Handler Code
```go
{
	var params model.StatementOfUseDetailRequest
	err := validation.GetQueryParamsHTTP(c, &params)
	if err != nil {
		return
	}

	params.PayCD = stringutils.MappingPayCD(params.Pay)
	resp, err := h.statementOfUseService.GetDetail(c.Request.Context(), params)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
		return
	}

	url, err := h.statementOfUseService.ExportToExcelDetail(c.Request.Context(), resp)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse([]string{url}))
}
```

## Detected Service Calls

- `statementOfUseService.GetDetail()`
- `Request.Context()`
- `statementOfUseService.ExportToExcelDetail()`
