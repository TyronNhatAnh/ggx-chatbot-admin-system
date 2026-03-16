# HomeMovingEstimateGuest

## Endpoint
`POST /api/v1/guest/home-moving/estimate`

## Handler
- **Variable:** `homeMovingHandler`
- **Receiver type:** `HomeMovingHandler`
- **Method:** `HomeMovingEstimateGuest`

## File
`internal/api/http/v1/home_moving_handler.go`

## Handler Code
```go
{
	var req entities.HomeMovingEstimateRequest
	err := validation.CheckValidateHTTP(c, &req)
	if err != nil {
		return
	}
	logger.InfoCtx(c.Request.Context(), "Info Estimate", zap.Any("Request: ", req))

	res, errorCommon := h.homeMovingService.HomeMovingEstimate(c.Request.Context(), req)
	if errorCommon.Error != nil {
		httpcommon.ExposeError(c, errorCommon)
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(res))
}
```

## Detected Service Calls

- `homeMovingService.HomeMovingEstimate()`
