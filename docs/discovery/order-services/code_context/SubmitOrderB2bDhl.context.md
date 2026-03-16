# SubmitOrderB2bDhl

## Endpoint
`POST /api/v1/b2b-orders-dhl`

## Handler
- **Variable:** `orderNewHandler`
- **Receiver type:** `OrderNewHandler`
- **Method:** `SubmitOrderB2bDhl`

## File
`internal/api/http/v1/order_new_handler.go`

## Handler Code
```go
{
	var req []entities.OrderRequestB2BInfo
	err := validation.CheckValidateHTTP(c, &req)
	if err != nil {
		return
	}
	var orders []*entities.OrderResponseB2B

	id, err := httpcommon.GetUserId(c)
	if err != nil {
		logger.Error("GetUserId error ... : ", zap.Error(err))
		orders = h.getErrorSubmitOrderB2B(httpcommon.RequestInvalid, orders)
		c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(orders))
		return
	}
	users, err := h.baseService.UserClient.GetUsers(c, &grpc.GetUserRequest{
		Id: uint64(id),
	})
	if err != nil {
		logger.Error("GetUsers error ... : ", zap.Error(err))
		orders = h.getErrorSubmitOrderB2B(httpcommon.RequestInvalid, orders)
		c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(orders))
		return
	}

	orderRequestInfos, err := h.getOrderInfo(c, req, users)
	if err != nil {
		logger.Error("getOrderInfo error ... : ", zap.Error(err))
		orders = h.getErrorSubmitOrderB2B(httpcommon.RequestInvalid, orders)
		c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(orders))
		return
	}

	var mutex = &sync.Mutex{}
	gEstimate, _ := errgroup.WithContext(c)
	gEstimate.SetLimit(10)
	estimateDatasMapSync := make(map[int]*model.ResultOrderB2B)
	for i, v := range orderRequestInfos {
		i, v := i, v
		gEstimate.Go(func() error {
			var estimateData *model.ResultOrderB2B
			logger.Warn("Estimate Order - Starting ... : "+strconv.Itoa(i), zap.Error(err))
			data, err := h.getPriceEstimateB2BDhl(c, v, users)
			if err == nil {
				estimateData = &model.ResultOrderB2B{
					EstimateData:     data,
					OrderRequestInfo: v,
					Success:          true,
				}
			} else {
				estimateData = &model.ResultOrderB2B{
					Reason:  err.Error(),
					Success: false,
				}
			}
			logger.Warn("Estimate Order - Done ... : "+strconv.Itoa(i), zap.Error(err))
			mutex.Lock()
			estimateDatasMapSync[i] = estimateData
			mutex.Unlock()
			return nil
		})
	}
	if err = gEstimate.Wait(); err != nil {
		logger.Warn("getPriceEstimate error", zap.Error(err))
	}

	ordersMapSync := make(map[int]*entities.OrderResponseB2B)
	for i, v := range estimateDatasMapSync {
		startSubmit := time.Now()

		var order *entities.OrderResponseB2B
		if v.Success {
			logger.Warn("Submit Order -- Starting ... : "+strconv.Itoa(i)+":"+startSubmit.Format(constants.Date_Format), zap.Error(err))
			data, existed, err := h.orderNewService.SubmitOrderB2bDhl(c.Request.Context(), v.OrderRequestInfo, users, v.EstimateData)
			if err == nil {
				order = &entities.OrderResponseB2B{
					OrderId: &data.Id,
					PieceId: orderRequestInfos[i].PieceId,
					Success: true,
					Existed: existed,
				}
			} else {
				order = &entities.OrderResponseB2B{
					Success: false,
					Reason:  &err.Message,
					PieceId: orderRequestInfos[i].PieceId,
				}
			}
		} else {
			order = &entities.OrderResponseB2B{
				Success: false,
				Reason:  &v.Reason,
				PieceId: orderRequestInfos[i].PieceId,
			}
		}

		logger.Warn("Submit Order -- Done ... : " + strconv.Itoa(i) + ":" + time.Since(startSubmit).String())
		ordersMapSync[i] = order
	}

	for _, v := range ordersMapSync {
		orders = append(orders, v)
	}

	go func() {
		requestNotification := []int64{}
		for _, v := range orders {
			if v.Success && !v.Existed {
				requestNotification = append(requestNotification, *v.OrderId)
			}
		}
		err := h.baseService.DaService.SendNotificationToDaApp(requestNotification)
		if err != nil {
			logger.Warn("SendNotification submit order dhl error", zap.Error(err))
		}
	}()

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(orders))
}
```

## Detected Service Calls

- `UserClient.GetUsers()`
- `orderNewService.SubmitOrderB2bDhl()`
- `DaService.SendNotificationToDaApp()`
