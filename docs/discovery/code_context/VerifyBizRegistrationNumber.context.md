# VerifyBizRegistrationNumber

## Endpoint
`GET /api/v1/guest/etax/verify_biz_registration_number/:biz_registration_number`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `Server`
- **Method:** `VerifyBizRegistrationNumber`

## File
`internal/api/grpc/order_grpc.go`

## Handler Code
```go
{
	response, err := s.OrderNewService.VerifyBizRegistrationNumber(ctx, request.BizRegistrationNumber)
	if err != nil {
		logger.Error("VerifyBizRegistrationNumber err ", zap.Error(err))
		return nil, err
	}

	regNums := make([]*pb.RegistrationNumberVerificationResult, len(response.RegistrationNumbers))
	for i := range response.RegistrationNumbers {
		r := response.RegistrationNumbers[i]
		regNums[i] = &pb.RegistrationNumberVerificationResult{
			BusinessNumber: r.BusinessNumber,
			TaxpayerStatus: r.TaxpayerStatus,
			TaxpayerCode:   r.TaxpayerCode,
			TaxType:        r.TaxType,
			TaxpayerCD:     r.TaxpayerCD,
			EndDate:        r.EndDate,
			Valid:          r.Valid,
		}
	}

	return &pb.VerifyBizRegistrationNumberResponse{
		StatusCode:          response.StatusCode,
		RegistrationNumbers: regNums,
	}, nil
}
```

## Detected Service Calls

- `OrderNewService.VerifyBizRegistrationNumber()`
