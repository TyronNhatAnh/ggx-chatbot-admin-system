# TestAuth

## Endpoint
`GET /api/v1/test-auth`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `TestAuth`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	token := c.Request.Header.Get("Authorization")
	c.JSON(http.StatusOK, gin.H{
		"token": token,
	})
}
```

## Detected Service Calls

_No service calls detected._
