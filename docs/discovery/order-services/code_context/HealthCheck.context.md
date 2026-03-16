# HealthCheck

## Endpoint
`GET /api/v1/guest/health/check`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `HealthCheck`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse[any](nil))
}
```

## Detected Service Calls

_No service calls detected._
