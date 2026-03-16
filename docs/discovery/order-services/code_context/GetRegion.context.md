# GetRegion

## Endpoint
`GET /api/v1/guest/check-region`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `GetRegion`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	responseRegion, err := h.baseService.OtherService.GetRegionByRegionID(c.Request.Context(), model.RegionRequest{RegionID: 0})
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(responseRegion))
}
```

## Detected Service Calls

- `OtherService.GetRegionByRegionID()`
