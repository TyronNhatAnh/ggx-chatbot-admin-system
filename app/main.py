import logging
import math
import threading
import time
import uuid
from collections import defaultdict, deque

from google.api_core.exceptions import ResourceExhausted
from google.genai.errors import APIError
from fastapi import FastAPI, HTTPException, Request

from app.orchestrator.ai_orchestrator import AIOrchestrator
from app.observability import get_request_id, reset_request_id, set_request_id
from app.config import settings
from app.schemas.chat_schema import ChatRequest, ChatResponse

# ---------------------------------------------------------------------------
# Logging — configure once at process start so all modules inherit the format
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  [req_id=%(request_id)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


for _handler in logging.getLogger().handlers:
    _handler.addFilter(_RequestIdFilter())

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
_CHAT_API_KEY_HEADER = "x-api-key"
_REQUEST_ID_HEADER = "x-request-id"


class InMemoryFixedWindowRateLimiter:
    """Simple in-memory fixed-window limiter keyed by client identity."""

    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        self._max_requests = max(1, max_requests)
        self._window_seconds = max(1, window_seconds)
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.time()
        cutoff = now - self._window_seconds

        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self._max_requests:
                retry_after = max(1, math.ceil(self._window_seconds - (now - bucket[0])))
                return (False, retry_after)

            bucket.append(now)
            return (True, 0)


_rate_limiter_lock = threading.Lock()
_chat_rate_limiter: InMemoryFixedWindowRateLimiter | None = None
_chat_rate_limiter_cfg: tuple[int, int] | None = None


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


def _extract_chat_api_key(request: Request) -> str:
    """Accept API key from X-API-Key or Authorization: Bearer <key>."""
    header_key = (request.headers.get(_CHAT_API_KEY_HEADER) or "").strip()
    if header_key:
        return header_key

    auth_header = (request.headers.get("authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def _require_chat_auth(request: Request) -> None:
    if not settings.chat_auth_enabled:
        return

    expected_key = settings.chat_api_key.strip()
    if not expected_key:
        logger.error("[Auth    ] CHAT_AUTH_ENABLED=true but CHAT_API_KEY is not configured")
        raise HTTPException(status_code=500, detail="Chat authentication is not configured")

    provided_key = _extract_chat_api_key(request)
    if provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _get_chat_rate_limiter() -> InMemoryFixedWindowRateLimiter:
    global _chat_rate_limiter  # noqa: PLW0603
    global _chat_rate_limiter_cfg  # noqa: PLW0603

    cfg = (settings.chat_rate_limit_requests, settings.chat_rate_limit_window_seconds)
    with _rate_limiter_lock:
        if _chat_rate_limiter is None or _chat_rate_limiter_cfg != cfg:
            _chat_rate_limiter = InMemoryFixedWindowRateLimiter(
                max_requests=cfg[0],
                window_seconds=cfg[1],
            )
            _chat_rate_limiter_cfg = cfg
        return _chat_rate_limiter


def _reset_chat_rate_limiter() -> None:
    """Reset in-memory limiter state (used by tests)."""
    global _chat_rate_limiter  # noqa: PLW0603
    global _chat_rate_limiter_cfg  # noqa: PLW0603
    with _rate_limiter_lock:
        _chat_rate_limiter = None
        _chat_rate_limiter_cfg = None


def _client_identity(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _enforce_chat_rate_limit(request: Request) -> None:
    if not settings.chat_rate_limit_enabled:
        return

    allowed, retry_after = _get_chat_rate_limiter().allow(_client_identity(request))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded for /chat",
            headers={"Retry-After": str(retry_after)},
        )


# ---------------------------------------------------------------------------
# Middleware — log every request with method, path, and total wall time
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    request_id = (request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())).strip() or str(uuid.uuid4())
    token = set_request_id(request_id)
    try:
        logger.info("[Request ] %s %s", request.method, request.url.path)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        elapsed = time.perf_counter() - start
        logger.info(
            "[Response] %s %s  status=%s  elapsed=%.3fs",
            request.method, request.url.path, response.status_code, elapsed,
        )
        return response
    finally:
        reset_request_id(token)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple liveness probe."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest, http_request: Request):
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
    _require_chat_auth(http_request)
    _enforce_chat_rate_limit(http_request)

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
