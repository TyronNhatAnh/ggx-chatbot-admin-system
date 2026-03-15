# EstimateAuth

## Endpoint
`POST /api/v1/estimate`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `EstimateAuth`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	id, err := httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}

	h.Estimate(c, id)
}
```

## Detected Service Calls

_No service calls detected._
