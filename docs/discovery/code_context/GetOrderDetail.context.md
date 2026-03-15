# GetOrderDetail

## Endpoint
`GET /api/v1/orders/:orderId/admin`

## Handler
- **Variable:** `orderHandler`
- **Receiver type:** `Server`
- **Method:** `GetOrderDetail`

## File
`internal/api/grpc/order_grpc.go`

## Handler Code
```go
{
	orderDetail, err := s.OrderService.GetOrderDetailHandler.Handler(ctx, int64(request.OrderRequestId))
	if err != nil {
		logger.Error("GetOrderDetail err ", zap.Error(err))
		return nil, err
	}

	return &pb.GetOrderDetailResponse{
		ID:                             orderDetail.ID,
		ParentID:                       uint64(orderDetail.ParentID.Int64),
		DeviceID:                       uint64(orderDetail.DeviceID.Int64),
		PlatformID:                     uint64(orderDetail.PlatformCD),
		ExternalOrderID:                orderDetail.ExternalOrderID.String,
		AdminUserID:                    uint64(orderDetail.AdminUserID.Int64),
		VehiclePoolID:                  uint64(orderDetail.VehiclePoolID),
		PayCD:                          int32(orderDetail.PayCD),
		StatusCD:                       int32(orderDetail.StatusCD),
		HubYN:                          orderDetail.HubYN,
		AppointmentAt:                  orderDetail.AppointmentAt.UnixMilli(),
		VisibleAt:                      orderDetail.VisibleAt.Time.UnixMilli(),
		Quantity:                       uint32(orderDetail.Quantity),
		WaypointCount:                  uint32(orderDetail.WaypointCount),
		FromPlace:                      orderDetail.FromPlace,
		ToPlace:                        orderDetail.ToPlace,
		Remark:                         orderDetail.Remark.String,
		Notes:                          orderDetail.Notes.String,
		ResponsePossibleWithin5Minutes: uint32(orderDetail.ResponsePossibleWithin5Minutes.Int64),
		CompletedAt:                    orderDetail.CompletedAt.Time.UnixMilli(),
		CanceledAt:                     orderDetail.CancelledAt.Time.UnixMilli(),
		CreatedAt:                      orderDetail.CreatedAt.UnixMilli(),
		UpdatedAt:                      orderDetail.UpdatedAt.UnixMilli(),
		DeletedAt:                      orderDetail.DeletedAt.Time.UnixMilli(),
		OrderOwner: &pb.OrderOwner{
			OrderRequestID:   orderDetail.OrderOwnerList.OrderRequestID,
			OrganizationID:   uint64(orderDetail.OrderOwnerList.OrganizationID),
			BranchID:         uint64(orderDetail.OrderOwnerList.BranchID),
			UserID:           uint64(orderDetail.OrderOwnerList.UserID),
			Name:             orderDetail.OrderOwnerList.Name,
			ContactNo:        orderDetail.OrderOwnerList.ContactNo,
			OrganizationName: orderDetail.OrderOwnerList.OrganizationName,
			BranchName:       orderDetail.OrderOwnerList.BranchName,
			CreatedAt:        orderDetail.OrderOwnerList.CreatedAt.UnixMilli(),
			UpdatedAt:        orderDetail.OrderOwnerList.UpdatedAt.UnixMilli(),
			TypeCD:           int32(orderDetail.OrderOwnerList.TypeCD),
			Email:            orderDetail.OrderOwnerList.Email,
		},
		WaypointList: func(waypoints []entities.WaypointResponse) []*pb.Waypoint {
			waypointProtoList := make([]*pb.Waypoint, len(waypoints))
			for i, waypoint := range waypoints {
				waypointProtoList[i] = &pb.Waypoint{
					ID:             uint64(waypoint.ID),
					OrderRequestID: uint64(waypoint.OrderRequestID),
					Arrangement:    uint32(waypoint.Arrangement),
					StatusCD:       int32(waypoint.StatusCd),
					RequestedAt:    waypoint.RequestedAt.Time.UnixMilli(),
					ReachedAt:      waypoint.ReachedAt.Time.UnixMilli(),
					AddressID:      uint64(waypoint.AddressId.Int64),
					RegionID:       uint64(waypoint.RegionId),
					LocationLat:    int32(waypoint.LocationLat),
					LocationLon:    int32(waypoint.LocationLon),
					Distance:       uint64(waypoint.Distance.Int64),
					Reason:         waypoint.Reason.String,
					Remark:         waypoint.Remark.String,
					CreatedAt:      waypoint.CreatedAt.UnixMilli(),
					UpdatedAt:      waypoint.UpdatedAt.UnixMilli(),
					DeletedAt:      waypoint.DeletedAt.Time.UnixMilli(),
				}
			}
			return waypointProtoList
		}(orderDetail.WaypointList),
		OrderFlagList: func(flags []order_detail.OrderFlag) []*pb.OrderFlag {
			flagsProto := make([]*pb.OrderFlag, len(flags))
			for i, flag := range flags {
				flagsProto[i] = &pb.OrderFlag{
					OrderRequestID: flag.OrderRequestID,
					TypeCD:         int32(flag.TypeCD),
					CreatedAt:      flag.CreatedAt.UnixMilli(),
					DeletedAt:      flag.DeletedAt.Time.UnixMilli(),
				}
			}
			return flagsProto
		}(orderDetail.OrderFlagList),
		OrderAmount: func(amounts []order_detail.OrderAmount) []*pb.OrderAmount {
			amountsProto := make([]*pb.OrderAmount, len(amounts))
			for i, amount := range amounts {
				amountsProto[i] = &pb.OrderAmount{
					ID:             uint64(amount.ID),
					OrderRequestID: uint64(amount.OrderRequestID.Int64),
					TargetCD:       int32(amount.TargetCD),
					PriceCD:        int32(amount.PriceCD),
					PriceCDName:    amount.PriceCDName,
					PriceID:        uint64(amount.PriceID.Int64),
					PriceUnit:      uint64(amount.PriceUnit.Int64),
					Title:          amount.Title,
					Amount:         amount.Amount,
					RefPriceCD:     int32(amount.RefPriceCD.Int64),
					Priority:       int32(amount.Priority),
					CreatedAt:      amount.CreatedAt.UnixMilli(),
					UpdatedAt:      amount.UpdatedAt.UnixMilli(),
					DeletedAt:      amount.DeletedAt.Time.UnixMilli(),
				}
			}
			return amountsProto
		}(orderDetail.OrderAmount),
		AppliedExtra: func(extras []order_detail.AppliedExtra) []*pb.AppliedExtra {
			extrasProto := make([]*pb.AppliedExtra, len(extras))
			for i, extra := range extras {
				extrasProto[i] = &pb.AppliedExtra{
					OrderRequestID: extra.OrderRequestID,
					ExtraPriceID:   int32(extra.ExtraPriceID),
					Quantity:       int32(extra.Quantity),
					CreatedAt:      extra.CreatedAt.UnixMilli(),
					UpdatedAt:      extra.UpdatedAt.UnixMilli(),
					DeletedAt:      extra.DeletedAt.Time.UnixMilli(),
				}
			}
			return extrasProto
		}(orderDetail.AppliedExtra),
	}, nil
}
```

## Detected Service Calls

- `GetOrderDetailHandler.Handler()`
- `AppointmentAt.UnixMilli()`
- `Time.UnixMilli()`
- `CreatedAt.UnixMilli()`
- `UpdatedAt.UnixMilli()`
