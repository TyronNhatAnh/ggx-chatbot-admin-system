from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's query for the admin assistant.",
        examples=["What is the status of order ORD-002?"],
    )
    conversation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description=(
            "Optional conversation identifier used to preserve short context "
            "across multiple /chat requests."
        ),
    )
    service_token: str = Field(
        ...,
        min_length=1,
        description=(
            "Bearer token forwarded to downstream user/order services for this request. "
            "Accepts raw token or 'Bearer <token>'."
        ),
        examples=["Bearer eyJhbGciOi..."],
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="The AI assistant's answer.")
    tools_called: list[str] = Field(
        default_factory=list,
        description="Names of the tools the AI invoked to answer the query.",
    )
    conversation_id: str | None = Field(
        default=None,
        description="Conversation identifier to reuse in follow-up requests.",
    )
