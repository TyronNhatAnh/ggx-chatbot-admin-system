from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's query for the admin assistant.",
        examples=["What is the status of order ORD-002?"],
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="The AI assistant's answer.")
    tools_called: list[str] = Field(
        default_factory=list,
        description="Names of the tools the AI invoked to answer the query.",
    )
