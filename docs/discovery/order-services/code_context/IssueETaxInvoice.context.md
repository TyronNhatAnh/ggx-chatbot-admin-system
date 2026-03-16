# IssueETaxInvoice

## Endpoint
`POST /api/v1/guest/etax/issue_tax_invoice`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `IssueETaxInvoice`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	var request model.IssueETaxInvoiceRequest
	err := validation.CheckValidateHTTP(c, &request)
	if err != nil {
		return
	}
	logger.InfoCtx(c.Request.Context(), "OrderNewHandler.IssueETaxInvoice", zap.Any("Request: ", request))

	// Call the DaService to issue the e-tax invoice
	response, err := h.baseService.DaService.IssueETaxInvoice(request)
	if err != nil {
		logger.ErrorCtx(c.Request.Context(), "Failed to issue e-tax invoice", zap.Error(err))
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(
			httpcommon.RequestInvalid,
			httpcommon.OrderETaxInvalid,
			"orderRequestId",
		))
		return
	}

	if !response.Result {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(
			response.Reason,
			httpcommon.OrderETaxInvalid,
			"orderRequestId",
		))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse[any](true))
}
```

## Detected Service Calls

- `DaService.IssueETaxInvoice()`
