# VerifyBizRegistrationNumber

## Endpoint
`GET /api/v1/guest/etax/verify_biz_registration_number/:biz_registration_number`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `VerifyBizRegistrationNumber`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	bizRegNumber := c.Param("biz_registration_number")
	if bizRegNumber == "" {
		logger.ErrorCtx(c.Request.Context(), "Business registration number is required")
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.BizRegNumberInvalidMsg, httpcommon.BizRegistrationNumberInvalid, "biz_registration_number"))
		return
	}

	var userID int64
	var driver *grpc.GetUserDriverResponse
	if userIDStr := c.Query("userId"); userIDStr != "" {
		parsed, err := strconv.ParseInt(userIDStr, 10, 64)
		if err != nil {
			c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(
				"invalid userID",
				httpcommon.RequestInvalid,
				"userID",
			))
			return
		}
		userID = parsed
	}

	logger.InfoCtx(c.Request.Context(), "OrderNewHandler.VerifyBizRegistrationNumber", zap.String("bizRegNumber", bizRegNumber), zap.Int64("userId", userID))

	if userID != 0 {
		var err error
		driver, err = h.baseService.UserDriverClient.GetUserDriver(c, &grpc.GetUserDriverRequest{
			Id: uint64(userID),
		})
		if err != nil {
			logger.ErrorCtx(c.Request.Context(), "Failed to get driver info", zap.Error(err))
			c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.BizRegNumberInvalidMsg, httpcommon.BizRegistrationNumberUserInvalid, "userID"))
			return
		}

		if driver.BizRegistrationNumber != bizRegNumber {
			logger.ErrorCtx(c.Request.Context(), "Business registration number does not match with user", zap.String("bizRegNumber", bizRegNumber), zap.Int64("userId", userID))
			c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.BizRegNumberInvalidMsg, httpcommon.BizRegistrationNumberUserInvalid, "biz_registration_number"))
			return
		}
	}

	response, err := h.orderNewService.VerifyBizRegistrationNumber(c.Request.Context(), bizRegNumber)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.BizRegNumberInvalidMsg, httpcommon.BizRegistrationNumberInvalid, "biz_registration_number"))
		return
	}

	if driver != nil {
		response.DriverInfo = &model.BizNumberVerifyDriverInfo{}
		response.DriverInfo.Id = driver.Id
		response.DriverInfo.Name = driver.Name
		response.DriverInfo.Email = driver.Email
		response.DriverInfo.BizRegistrationNumber = driver.BizRegistrationNumber
		response.DriverInfo.CompanyName = driver.NameOfCompany
		response.DriverInfo.TaxPlayerCd = driver.TaxPlayerCD
		response.DriverInfo.TaxPlayerTitle = driver.TaxPlayerTitle
	}

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(response))
}
```

## Detected Service Calls

- `UserDriverClient.GetUserDriver()`
- `orderNewService.VerifyBizRegistrationNumber()`
