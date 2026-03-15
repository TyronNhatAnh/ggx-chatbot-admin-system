import logging
import time

from google.api_core.exceptions import ResourceExhausted
from google.genai.errors import APIError
from fastapi import FastAPI, HTTPException, Request

from app.orchestrator.ai_orchestrator import AIOrchestrator
from app.schemas.chat_schema import ChatRequest, ChatResponse

# ---------------------------------------------------------------------------
# Logging — configure once at process start so all modules inherit the format
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

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

_orchestrator: AIOrchestrator | None = None


def _is_gemini_quota_error(exc: Exception) -> bool:
    """Detect quota/rate-limit style errors from Gemini SDK variants."""
    if isinstance(exc, ResourceExhausted):
        return True
    if isinstance(exc, APIError):
        status = (exc.status or "").upper()
        return exc.code == 429 or status == "RESOURCE_EXHAUSTED"
    text = str(exc).upper()
    return "429" in text and "RESOURCE_EXHAUSTED" in text


def _quota_error_message(exc: Exception) -> str:
    if isinstance(exc, APIError) and exc.message:
        return f"Gemini quota exceeded: {exc.message}"
    return "Gemini quota exceeded. Please retry later or switch to a model/quota tier with higher limits."


def get_orchestrator() -> AIOrchestrator:
    """Return a singleton orchestrator instance, lazily created on first use."""
    global _orchestrator  # noqa: PLW0603
    if _orchestrator is None:
        logger.info("[Startup] Initialising AIOrchestrator...")
        _orchestrator = AIOrchestrator()
        logger.info("[Startup] AIOrchestrator ready.")
    return _orchestrator


# ---------------------------------------------------------------------------
# Middleware — log every request with method, path, and total wall time
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    logger.info("[Request ] %s %s", request.method, request.url.path)
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    logger.info(
        "[Response] %s %s  status=%s  elapsed=%.3fs",
        request.method, request.url.path, response.status_code, elapsed,
    )
    return response


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
    preview = request.message[:120].replace("\n", " ")
    logger.info(
        "[Chat    ] message: \"%s%s\"  conversation_id=%s",
        preview,
        "..." if len(request.message) > 120 else "",
        request.conversation_id or "<new>",
    )
    try:
        reply, tools_called, conversation_id = get_orchestrator().chat(
            request.message,
            request.conversation_id,
        )
        logger.info("[Chat    ] done  tools_called=%s  conversation_id=%s", tools_called, conversation_id)
        return ChatResponse(reply=reply, tools_called=tools_called, conversation_id=conversation_id)
    except ValueError as exc:
        logger.error("[Chat    ] ValueError: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        if _is_gemini_quota_error(exc):
            logger.warning("[Chat    ] Gemini quota exhausted: %s", exc)
            raise HTTPException(status_code=429, detail=_quota_error_message(exc))

        logger.error("[Chat    ] Unexpected error: %s: %s", type(exc).__name__, exc)
        raise HTTPException(status_code=500, detail="Internal server error")
