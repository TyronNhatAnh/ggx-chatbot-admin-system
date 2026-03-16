# CreateFilterSet

## Endpoint
`POST /api/v1/order-control/filter-set/create`

## Handler
- **Variable:** `orderControlHandler`
- **Receiver type:** `OrderControlHandler`
- **Method:** `CreateFilterSet`

## File
`internal/api/http/v1/order_control_handler.go`

## Handler Code
```go
{
	var (
		params      = entities.FilterSetMeta{}
		adminUserID int64
	)

	err := validation.CheckValidateHTTP(c, &params)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.ErrorMapData, ""))
		return
	}

	adminUserID, err = httpcommon.GetAdminID(c)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.RequestInvalid, "adminID"))
		return
	}

	resp, err := h.service.CreateFilterSetHandler.Handle(c.Request.Context(), uint64(adminUserID), params)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(resp))
}
```

## Detected Service Calls

- `CreateFilterSetHandler.Handle()`
