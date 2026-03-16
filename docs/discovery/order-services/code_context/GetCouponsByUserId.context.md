# GetCouponsByUserId

## Endpoint
`GET /api/v1/coupons`

## Handler
- **Variable:** `couponNewHandler`
- **Receiver type:** `CouponHandler`
- **Method:** `GetCouponsByUserId`

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

	var req model.GetCouponsByUserIdRequest
	err = validation.GetQueryParamsHTTP(c, &req)
	if err != nil {
		return
	}

	resp, respErr := h.couponService.GetCouponsByUserId(c.Request.Context(), uint64(userID), &req)
	if respErr.Error != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(respErr.Error.Error(), httpcommon.SystemError, ""))
		return
	}

	c.JSON(http.StatusOK, httpcommon.NewPagingSuccessResponseWithMeta(resp.CouponList, resp.Meta))
}
```

## Detected Service Calls

- `couponService.GetCouponsByUserId()`
