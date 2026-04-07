from pydantic import BaseModel, Field


class TurnResponse(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str
    tools_called: list[str] = Field(default_factory=list)
    created_at: float = Field(..., description="Unix timestamp")


class MemoryItemResponse(BaseModel):
    id: str
    type: str = Field(..., description="'fact' | 'entity' | 'decision'")
    content: str
    created_at: float


class ConversationSummaryResponse(BaseModel):
    conversation_id: str
    summary: str = ""
    updated_at: float
    turn_count: int


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummaryResponse]
    total: int
    page: int
    page_size: int


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    summary: str = ""
    turns: list[TurnResponse]
    memory: list[MemoryItemResponse] = Field(default_factory=list)
    updated_at: float


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=8000,
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
