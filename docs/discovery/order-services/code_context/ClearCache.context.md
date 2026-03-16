# ClearCache

## Endpoint
`GET /api/v1/guest/clear-cache`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `ClearCache`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	// h.baseService.RedisClient.FlushAll(c)
	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(""))
}
```

## Detected Service Calls

- `RedisClient.FlushAll()`
