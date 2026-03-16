# GetReconciliationUrl

## Endpoint
`POST /api/v1/file/reconciliation`

## Handler
- **Variable:** `fileHandler`
- **Receiver type:** `FileHandler`
- **Method:** `GetReconciliationUrl`

## File
`internal/api/http/v1/file_handler.go`

## Handler Code
```go
{
	var request reconciliation.ReconciliationRequest
	if err := validation.CheckValidateHTTP(c, &request); err != nil {
		return
	}
	logger.InfoCtx(c.Request.Context(), "Info GetReconciliationUrl", zap.Any("ReconciliationRequest: ", request))

	var resp *reconciliation.ReconciResponse
	resp, err := h.f.GetReconciliationUrlHandler.Handle(c.Request.Context(), request)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), "failed to get Reconciliation url", ""))
		return
	}
	logger.InfoCtx(c.Request.Context(), "Info GetReconciliationUrl", zap.Any("Response: ", resp))

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(resp))
}
```

## Detected Service Calls

- `GetReconciliationUrlHandler.Handle()`
