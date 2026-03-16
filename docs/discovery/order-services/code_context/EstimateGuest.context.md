# EstimateGuest

## Endpoint
`POST /api/v1/guest/estimate`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `OrderHandler`
- **Method:** `EstimateGuest`

## File
`internal/api/http/v1/order_handler.go`

## Handler Code
```go
{
	h.Estimate(c, 0)
}
```

## Detected Service Calls

_No service calls detected._
