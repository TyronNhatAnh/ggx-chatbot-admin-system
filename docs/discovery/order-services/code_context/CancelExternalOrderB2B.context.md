# CancelExternalOrderB2B

## Endpoint
`POST /api/v1/orders/external/:orderId/b2b-cancel`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `CancelExternalOrderB2B`

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
		h.cancelOrder(c, userId, true, constants.RoleAdminUser)
		return
	}
	if utils.Contains(roles, constants.RoleB2BMaster) {
		h.cancelOrder(c, userId, true, constants.RoleB2BMaster)
		return
	}
	c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(constants.CancelPermissionError, httpcommon.SystemError, ""))
}
```

## Detected Service Calls

_No service calls detected._
