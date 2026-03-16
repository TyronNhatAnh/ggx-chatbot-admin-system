# GetSummary

## Endpoint
`GET /api/v1/report/statement-of-use/summary`

## Handler
- **Variable:** `reportNewHandler`
- **Receiver type:** `ReportHandler`
- **Method:** `GetSummary`

## File
`internal/api/http/v1/report_handler.go`

## Handler Code
```go
{
	var request model.StatementOfUseSummaryRequest
	err := validation.GetQueryParamsHTTP(c, &request)
	if err != nil {
		return
	}

	request.PayCD = stringutils.MappingPayCD(request.Pay)
	resp, err := h.statementOfUseService.GetSummary(c.Request.Context(), request)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
		return
	}
	resp.AdditionalData.Header = []string{"기업ID", "기업코드", "기업명", "거래유형", "주문", "고객운임", "고객 보너스"}
	c.JSON(http.StatusOK, httpcommon.NewPagingSuccessResponse(resp.Detail, 0, resp.AdditionalData))
}
```

## Detected Service Calls

- `statementOfUseService.GetSummary()`
