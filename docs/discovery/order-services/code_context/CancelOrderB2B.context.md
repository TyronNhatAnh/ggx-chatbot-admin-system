# CancelOrderB2B

## Endpoint
`POST /api/v1/orders/:orderId/b2b-cancel`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `CancelOrderB2B`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	userId, err := httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusUnauthorized, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}
	roles, err := h.getRoles(c, userId)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}

	// check role
	if utils.Contains(roles, constants.RoleAdminUser) {
		h.cancelOrder(c, userId, false, constants.RoleAdminUser)
		return
	}
	if utils.Contains(roles, constants.RoleB2BMaster) {
		h.cancelOrder(c, userId, false, constants.RoleB2BMaster)
		return
	}
	c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(constants.CancelPermissionError, httpcommon.RequestInvalid, ""))
}
```

## Detected Service Calls

_No service calls detected._
