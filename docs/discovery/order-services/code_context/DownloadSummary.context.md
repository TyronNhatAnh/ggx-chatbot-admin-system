# DownloadSummary

## Endpoint
`GET /api/v1/report/statement-of-use/summary/download`

## Handler
- **Variable:** `reportNewHandler`
- **Receiver type:** `ReportHandler`
- **Method:** `DownloadSummary`

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

	// validate pay only accept Credit
	if !stringutils.ContainsStringFold(request.Pay, orderconstants.PayCDName.Credit) || len(request.Pay) != 1 {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.PayCDOnlyCredit, httpcommon.RequestInvalid, "pay"))
		return
	}

	resp, err := h.statementOfUseService.GetSummaryDownload(c.Request.Context(), request)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
		return
	}

	urls := make([]string, len(resp))
	for i, detail := range resp {
		respDetail, err := h.statementOfUseService.GetDetail(c.Request.Context(), model.StatementOfUseDetailRequest{
			FromDate:       detail.FromDate,
			ToDate:         detail.ToDate,
			OrganizationID: detail.OrganizationId,
			BusinesslineCD: detail.BusinessLineCd,
			PayCD:          []string{"2"},
			Pay:            []string{orderconstants.PayCDName.Credit},
		})
		if err != nil {
			c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
			return
		}

		if len(respDetail.DetailData) == 0 {
			continue
		}

		urls[i], err = h.statementOfUseService.ExportToExcelSummary(c.Request.Context(), respDetail, &detail)
		if err != nil {
			c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, ""))
			return
		}
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(urls))
}
```

## Detected Service Calls

- `statementOfUseService.GetSummaryDownload()`
- `statementOfUseService.GetDetail()`
- `statementOfUseService.ExportToExcelSummary()`
