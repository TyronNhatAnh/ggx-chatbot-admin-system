# GetPresignedUrl

## Endpoint
`POST /api/v1/file/presigned`

## Handler
- **Variable:** `fileHandler`
- **Receiver type:** `FileHandler`
- **Method:** `GetPresignedUrl`

## File
`internal/api/http/v1/file_handler.go`

## Handler Code
```go
{
	var request presigned.PresignedRequest
	if err := validation.CheckValidateHTTP(c, &request); err != nil {
		return
	}
	logger.Info("Info GetPresignedUrl", zap.Any("PresignedRequest: ", request))

	id, err := httpcommon.GetUserId(c)
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.UserIsNotExist, constants.UserInvalid, "userId"))
		return
	}
	user, err := h.userClient.GetUsers(c, &grpcUser.GetUserRequest{
		Id: uint64(id),
	})
	if err != nil {
		c.JSON(http.StatusBadRequest, httpcommon.NewErrorResponse(httpcommon.UserIsNotExist, constants.UserInvalid, "userId"))
		return
	}

	var resp *presigned.PresignedResponse
	resp, err = h.f.GetPresignedUrlHandler.Handle(c.Request.Context(), request, user.Id)
	if err != nil {
		c.JSON(http.StatusInternalServerError, httpcommon.NewErrorResponse(err.Error(), "failed to get presigned url", ""))
		return
	}
	logger.Info("Info GetPresignedUrl", zap.Any("Response: ", resp))

	c.JSON(http.StatusOK, httpcommon.NewSuccessResponse(resp))
}
```

## Detected Service Calls

- `userClient.GetUsers()`
- `GetPresignedUrlHandler.Handle()`
- `Request.Context()`
