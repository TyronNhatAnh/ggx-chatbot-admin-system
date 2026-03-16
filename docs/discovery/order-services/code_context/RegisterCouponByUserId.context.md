# RegisterCouponByUserId

## Endpoint
`POST /api/v1/coupons/register-user`

## Handler
- **Variable:** `couponNewHandler`
- **Receiver type:** `CouponHandler`
- **Method:** `RegisterCouponByUserId`

## File
`internal/api/http/v1/coupon.go`

## Handler Code
```go
{
	userID, err := httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(err.Error(), httpcommon.SystemError, ""))
		return
	}

	var req model.RegisterCouponByUserIdRequest
	err = validation.CheckValidateHTTP(c, &req)
	if err != nil {
		return
	}

	respErr := h.couponService.RegisterCouponByUserId(c.Request.Context(), userID, &req)
	if respErr.Error != nil {
		if respErr.IsSystemError {
			c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(respErr.Error.Error(), httpcommon.SystemError, respErr.Field))
			return
		} else {
			c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(respErr.Error.Error(), httpcommon.RequestInvalid, respErr.Field))
			return
		}

	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(""))
}
```

## Detected Service Calls

- `couponService.RegisterCouponByUserId()`
