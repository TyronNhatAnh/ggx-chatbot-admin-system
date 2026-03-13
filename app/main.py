from fastapi import FastAPI, HTTPException

from app.orchestrator.ai_orchestrator import AIOrchestrator
from app.schemas.chat_schema import ChatRequest, ChatResponse

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Admin Assistant",
    description=(
        "A read-only AI assistant for querying logistics data such as "
        "orders, drivers, and analytics. Powered by Google Gemini."
    ),
    version="1.0.0",
)

# Initialise the orchestrator once at startup.
# It loads the Gemini model and registers all tools.
orchestrator = AIOrchestrator()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple liveness probe."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send a message to the AI admin assistant.

    The assistant uses internal tools to look up real data and returns
    a factual, concise answer. It will never modify system data.

    **Flow:**
    1. Receive user message.
    2. Build system prompt.
    3. Send message to Gemini.
    4. Detect tool calls in the response.
    5. Execute each tool.
    6. Send tool results back to Gemini.
    7. Return final answer.
    """
    try:
        reply, tools_called = orchestrator.chat(request.message)
        return ChatResponse(reply=reply, tools_called=tools_called)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
