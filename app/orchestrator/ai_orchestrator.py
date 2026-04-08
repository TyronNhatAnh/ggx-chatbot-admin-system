from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from datetime import date, timedelta
from typing import Any

from google.genai import types

from app.config import settings
from app.llm.gemini_client import GeminiChatFactory, create_gemini_model
from app.llm.vertex_credentials import create_vertex_client
from app.orchestrator.context_builder import build_history
from app.orchestrator.memory_service import MemoryService
from app.orchestrator.summarizer import summarize_conversation
from app.prompts.builder import build_system_prompt
from app.tools import ALL_TOOL_FUNCTIONS, FLASH_TOOL_SETS, TOOL_REGISTRY

logger = logging.getLogger(__name__)
MAX_TOOL_LOOPS = 6      # max tool-result round-trips; synthesis fallback is outside this cap (MAX_TOOL_LOOPS+2 worst case)
# Accept explicit ORD-* IDs or numeric IDs only.
# Prevent false positives like organization names (e.g. "DHLSC").
ORDER_ID_PATTERN = re.compile(r"\b(?:ORD-[A-Za-z0-9-]{3,}|\d{5,})\b", re.IGNORECASE)

# Pro model only handles knowledge-code.
# Give it only the tools it needs to reduce schema tokens (~5k → ~1.5k).
_PRO_TOOL_NAMES: frozenset[str] = frozenset({
    # org lookup
    "search_organizations",
    "get_organization_by_id",
    # knowledge tools
    "lookup_enum",
    "explain_status",
    "trace_service_flow",
    "get_struct_definition",
    "search_codebase",
    "traverse_graph",
    "find_api_consumers",
    "trace_full_stack",
    "get_knowledge_stats",
    # docs tools (used by knowledge-code)
    "list_available_docs",
    "search_endpoints",
    "get_handler_context",
})
_PRO_TOOLS: list = [fn for fn in ALL_TOOL_FUNCTIONS if fn.__name__ in _PRO_TOOL_NAMES]

_fallback_counters = {
    "max_tool_loop": 0,
    "repetitive_tool_calls": 0,
}
_fallback_counter_lock = threading.Lock()
# Markers we inject ourselves; strip them from user input to prevent prompt injection.
_INJECTION_PATTERN = re.compile(r"\[\s*(?:Instruction|Today's date)\s*:", re.IGNORECASE)
# Lines that look like model "thinking out loud" leaked into a text part rather than a thought part.
# Strip them from the final response so admins never see raw internal reasoning.
_REASONING_LEAK_RE = re.compile(
    r"^(?:"
    r"Wait[,.]?\s"
    r"|I'?ll\s+try\s+to\s"
    r"|I'?ll\s+assume\s"
    r"|Also[,.]?\s+I'?ll?\s+try"
    r"|I\s+will\s+make\s+sure\b"
    r"|I\s+will\s+(?:use|create|write|format|provide|output|include|show|display|map|list|note|add|check|double)\b"
    r"|Let(?:'s|\s+me)\s+(?:write|check|create|format|provide|output|map|list|make|double|think|look|see|use|show|display)\b"
    r"|I\s+will\s+also\b"
    r")",
    re.IGNORECASE,
)
# Threshold: a run of this many consecutive meta-commentary lines triggers block removal.
_REASONING_BLOCK_THRESHOLD = 4

def _sanitize_response(text: str) -> str:
    """Detect and strip pathological response artifacts.

    With include_thoughts=True the API routes all internal reasoning into
    thought-flagged parts that _response_text() already filters out before
    this function is ever called.  Two residual cases still need handling:

    1. Line-level leaks — individual lines of deliberation that slipped into
       a non-thought part ("Wait, I'll try...", "I will make sure...", etc.).
    2. Block-level leaks — a consecutive run of meta-commentary lines; strip
       from the first line of the block to the end of the block.
    3. Echo/parrot loop — the same line appears 3+ times.
    """
    if not text:
        return text

    lines = text.split("\n")

    # --- Pass 1: block-level reasoning dump detection ---
    # If _REASONING_BLOCK_THRESHOLD or more consecutive lines all look like
    # internal deliberation, strip the entire block.  Walking the line array
    # once is enough; we rebuild lines[] at the end if anything was removed.
    clean_lines: list[str] = []
    run_start: int | None = None
    block_stripped = 0
    for idx, ln in enumerate(lines):
        stripped = ln.strip()
        if _REASONING_LEAK_RE.match(stripped):
            if run_start is None:
                run_start = idx
        else:
            if run_start is not None:
                run_len = idx - run_start
                if run_len >= _REASONING_BLOCK_THRESHOLD:
                    block_stripped += run_len
                    # Don't append the run — discard it
                else:
                    # Short run: keep individual lines (may be legitimate)
                    clean_lines.extend(lines[run_start:idx])
                run_start = None
            clean_lines.append(ln)
    # Handle a trailing run
    if run_start is not None:
        run_len = len(lines) - run_start
        if run_len >= _REASONING_BLOCK_THRESHOLD:
            block_stripped += run_len
        else:
            clean_lines.extend(lines[run_start:])

    if block_stripped:
        logger.warning(
            "[Sanitize ] Stripped %d-line reasoning block from response.",
            block_stripped,
        )
        lines = clean_lines
        text = "\n".join(lines).strip()
        if not text or len(text) < 20:
            return ""

    # --- Pass 2: line-level reasoning leak (short individual lines) ---
    leaked = [ln for ln in lines if _REASONING_LEAK_RE.match(ln.strip())]
    if leaked:
        logger.warning(
            "[Sanitize ] Stripped %d reasoning-leak line(s) from response.",
            len(leaked),
        )
        lines = [ln for ln in lines if not _REASONING_LEAK_RE.match(ln.strip())]
        text = "\n".join(lines).strip()
        if not text or len(text) < 20:
            return ""

    # --- Pass 3: echo/parrot loop (same line ≥ 3 times) ---
    line_counts = Counter(ln.strip() for ln in lines if ln.strip())
    repeated = {ln for ln, cnt in line_counts.items() if cnt >= 3}
    if repeated:
        logger.warning(
            "[Sanitize ] Detected %d repeated line(s) in response (max count=%d). Stripping.",
            len(repeated), max(line_counts[ln] for ln in repeated),
        )
        clean = [ln for ln in lines if ln.strip() not in repeated]
        salvaged = "\n".join(clean).strip()
        return salvaged if salvaged and len(salvaged) > 20 else ""

    # --- Pass 4: intra-text phrase repetition loop ---
    # Catches patterns like "Foo Bar Baz . X Y Foo Bar Baz . X Y Foo Bar Baz ..."
    # where a short ngram repeats many times within the text (even on a single line).
    # This targets model hallucination loops that produce struct-field-like noise.
    _MD_TABLE_TOKEN_RE = re.compile(r"^[|:\-]+$")  # matches |, :---, ---, :-:, etc.
    # Count non-separator table data rows to distinguish table column repetition
    # from hallucination loops (e.g. "| Apr 7," legitimately repeats once per row).
    _MD_DATA_ROW_RE = re.compile(r"^\s*\|(?![\s|:\-]*\|?\s*$)")
    table_data_rows = sum(1 for ln in lines if _MD_DATA_ROW_RE.match(ln))
    words = text.split()
    if len(words) >= 20:
        for ngram_size in (3, 4, 5):
            ngram_counts: Counter[tuple[str, ...]] = Counter(
                tuple(words[i: i + ngram_size]) for i in range(len(words) - ngram_size + 1)
            )
            max_phrase, max_count = ngram_counts.most_common(1)[0]
            if max_count >= 5:
                # Don't discard responses where the only repeated ngram is
                # markdown table alignment syntax (e.g. "| :--- |" in wide tables).
                if all(_MD_TABLE_TOKEN_RE.match(tok) for tok in max_phrase):
                    continue
                # Don't discard table responses where the ngram is a column value
                # repeating once per data row (e.g., "| Apr 7," in a date column).
                # A true hallucination loop would repeat far more than one-per-row.
                if max_phrase[0] == "|" and table_data_rows >= 5 and max_count <= table_data_rows:
                    continue
                logger.warning(
                    "[Sanitize ] Detected phrase-repetition loop (%dx '%s'). Discarding response.",
                    max_count, " ".join(max_phrase),
                )
                return ""

    return text


def _sanitize_user_message(message: str) -> str:
    """Neutralize user-supplied text that impersonates internal prompt directives."""
    return _INJECTION_PATTERN.sub("[~", message)


def _response_parts(response: types.GenerateContentResponse) -> list[types.Part]:
    """Extract parts from the first candidate safely."""
    if not response.candidates:
        return []
    content = response.candidates[0].content
    if not content or not content.parts:
        return []
    return list(content.parts)


def _response_text(response: types.GenerateContentResponse) -> str:
    """Extract plain text response, always filtering thought parts.

    Never trust ``response.text`` alone — some SDK versions / model
    combinations include ``thought``-marked parts in that property.
    Iterate explicitly and exclude any part flagged as thinking.

    Intentionally returns empty string when the model produced only thought
    parts — the caller's empty-reply handler (synthesis fallback) handles
    that case correctly.  Falling back to ``response.text`` or leaking thought
    parts bypasses the synthesis fallback and sends raw reasoning to the user.
    """
    texts: list[str] = []
    for part in _response_parts(response):
        if part.text and not getattr(part, "thought", False):
            texts.append(part.text)
    return "\n".join(texts).strip()

def _normalize_order_id(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""

    upper = raw.upper()
    if upper.startswith("ORD-"):
        suffix = upper[4:]
        return upper if suffix and any(ch.isdigit() for ch in suffix) else ""

    if raw.isdigit() and len(raw) >= 5:
        return raw

    # Reject alpha-only labels (common org names/shortcodes).
    return ""

def _increment_fallback_counter(counter_name: str) -> int:
    with _fallback_counter_lock:
        _fallback_counters[counter_name] = _fallback_counters.get(counter_name, 0) + 1
        return _fallback_counters[counter_name]


def _current_fallback_counters() -> dict[str, int]:
    with _fallback_counter_lock:
        return dict(_fallback_counters)


def _log_structured_metrics(
    *,
    conversation_id: str,
    tools_called: list[str],
    gemini_calls: int,
    gemini_latency_seconds: float,
    tool_latency_seconds: float,
    total_latency_seconds: float,
    fallback_reason: str | None,
) -> None:
    payload = {
        "event": "chat_metrics",
        "conversation_id": conversation_id,
        "gemini_calls": gemini_calls,
        "tool_call_count": len(tools_called),
        "tool_unique_count": len(set(tools_called)),
        "latency_seconds": {
            "gemini": round(gemini_latency_seconds, 3),
            "tools": round(tool_latency_seconds, 3),
            "total": round(total_latency_seconds, 3),
        },
        "fallback_reason": fallback_reason,
        "fallback_counters": _current_fallback_counters(),
    }
    logger.info("[Metrics  ] %s", json.dumps(payload, sort_keys=True))



# ---------------------------------------------------------------------------
# Feature detection — keyword-based routing for modular prompt composition.
# Maps each feature domain to keywords (English + Korean).
# ---------------------------------------------------------------------------
_FEATURE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "order-lookup": (
        "order", "delivery", "coupon", "cancel fee", "reorder", "shipping record",
        "price estimate", "pricing", "invoice", "track",
        "đơn hàng", "đơn", "giao hàng", "vận chuyển", "hóa đơn", "mã đơn",
        "주문", "배달", "배송", "쿠폰", "취소",
    ),
    "driver-tracking": (
        "driver", "route", "tracking", "location", "fare", "online driver",
        "tài xế", "tài_xế", "vị trí", "lộ trình", "cước phí",
        "기사", "운전", "배차", "위치",
    ),
    "user-admin": (
        "user profile", "organization", "org", "branch", "admin role", "permission",
        "feature flag", "department", "account", "user",
        "tài khoản", "người dùng", "tổ chức", "chi nhánh", "phân quyền", "quyền",
        "사용자", "조직", "지점", "권한",
    ),
    "common-data": (
        "vehicle pool", "vehicle service", "vehicle prices", "vehicle type", "address search",
        "home moving", "ads", "common service",
        "xe", "loại xe", "địa chỉ", "chuyển nhà",
        "차량", "차종", "주소", "이사",
    ),
    "knowledge-code": (
        "enum", "status code", "struct", "handler", "service flow",
        "endpoint", "codebase", "api consumer", "graph", "code", "source", "flow",
        "mã", "luồng", "mã trạng thái",
    ),
    "email-dispatch": (
        "상차", "하차", "도착지", "수령인", "배차", "박스", "카고", "eta",
        "dispatch email", "email dispatch", "parse email", "email order",
        "email này", "đoạn email", "từ email", "parse email",
        "order#", "외부주문", "오더번호",
    ),
}


def _detect_feature_key(message: str) -> tuple[str | None, int]:
    """Detect the most likely feature domain from the user's message.

    Simple keyword scoring — no LLM call. Returns (key, score).
    Score is the number of matching keywords; 0 means no match.
    """
    lower = (message or "").lower()
    if not lower:
        return None, 0

    best_key: str | None = None
    best_score = 0
    for feature, keywords in _FEATURE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > best_score:
            best_score = score
            best_key = feature

    return best_key, best_score


class AIOrchestrator:
    """
    Manages the full conversation lifecycle with Gemini, including the
    tool-calling loop:

        send message
            → Gemini detects tool call needed
            → execute tool(s)
            → send results back to Gemini
            → get final plain-text answer
            → return to caller

    The loop repeats until Gemini produces a final text response with no
    further tool calls.
    """

    def __init__(self) -> None:
        # Shared Vertex AI client — single auth session for both models.
        shared_client = create_vertex_client()

        # Flash model — low latency, all tools, deterministic.
        # include_thoughts=True causes the API to route internal reasoning into
        # thought-flagged parts; _response_text() filters those out, so they
        # never reach the user.  Budget capped at 1 024 tokens — sufficient for
        # tool selection and response planning; 8 000 caused 30+ second latency
        # on simple lookups (model exhausted the budget even for trivial decisions).
        logger.info("[Orchestrator] Loading Flash model (%s) with %d tools...", settings.model_name, len(ALL_TOOL_FUNCTIONS))
        self._model = create_gemini_model(
            ALL_TOOL_FUNCTIONS,
            client=shared_client,
            temperature=0.0,
            max_output_tokens=4096,
            thinking_config=types.ThinkingConfig(include_thoughts=True, thinking_budget=1024),
        )

        # Pro model — deeper reasoning, scoped tool set, thinking enabled.
        # Falls back to Flash when pro_model_name is not configured.
        self._pro_model: "GeminiChatFactory | None" = None
        if not settings.pro_model_name:
            logger.warning(
                "[Orchestrator] PRO_MODEL_NAME not set — knowledge-code "
                "will use Flash instead.",
            )
        if settings.pro_model_name:
            logger.info(
                "[Orchestrator] Loading Pro model (%s) with %d scoped tools...",
                settings.pro_model_name, len(_PRO_TOOLS),
            )
            self._pro_model = create_gemini_model(
                _PRO_TOOLS,
                model_name=settings.pro_model_name,
                client=shared_client,
                temperature=0.0,
                max_output_tokens=8192,
                thinking_config=types.ThinkingConfig(include_thoughts=True, thinking_budget=-1),
            )
            logger.info("[Orchestrator] Pro model ready. Dual-model routing enabled.")

        # Bare Flash model — no tools, thinking disabled — used for conversational
        # turns (feature_key=None). Eliminates 38 tool schema tokens + 8k thinking
        # budget overhead when the admin sends a greeting or an unmatched question.
        logger.info("[Orchestrator] Loading bare Flash model for conversational turns...")
        self._bare_model = create_gemini_model(
            [],
            client=shared_client,
            temperature=0.0,
            max_output_tokens=2048,
            thinking_config=types.ThinkingConfig(include_thoughts=False, thinking_budget=0),
        )

        store = None
        if settings.chat_history_db:
            from app.persistence.chat_store import ChatStore
            store = ChatStore(settings.chat_history_db)

        self._memory = MemoryService(store=store)
        logger.info(
            "[Orchestrator] Ready.  Flash=%s (%d tools)  |  Pro=%s (%d tools)  |  Bare=%s (0 tools)  |  Routing=%s",
            settings.model_name,
            len(ALL_TOOL_FUNCTIONS),
            settings.pro_model_name if self._pro_model else "(disabled)",
            len(_PRO_TOOLS) if self._pro_model else 0,
            settings.model_name,
            "dual-model" if self._pro_model else "flash-only",
        )

    def chat(self, message: str, conversation_id: str | None = None) -> tuple[str, list[str], str]:
        """
        Send a user message and return the AI's reply with a list of tools used.

        Each call starts a fresh chat session. If ``conversation_id`` is
        provided, short context from recent turns is injected into the input
        to preserve continuity across requests.

        Args:
            message: The user's natural-language query.
            conversation_id: Optional conversation identifier from a previous
                             response.

        Returns:
            A tuple of (reply_text, tools_called, conversation_id) where
            tools_called is a list of function names that were invoked during
            this turn.

        Raises:
            ValueError: If Gemini requests a tool that is not in the registry.
        """
        total_start = time.perf_counter()
        session = self._memory.get_or_create(conversation_id)
        sid = session.session_id

        # Auto-extract entities from user message into long-term memory
        self._memory.extract_and_store_entities(sid, message)

        # Sanitize before embedding in LLM context to block prompt injection.
        safe_message = _sanitize_user_message(message)

        # Build native Gemini conversation history from the three memory layers.
        # History is seeded into the chat session; only the current message is sent fresh.
        history = build_history(sid, safe_message, self._memory)
        # Always inject today's date so Gemini can compute relative periods ("last 7 days", etc.).
        effective_message = f"[SYS:DATE={date.today().isoformat()}]\n\n{safe_message}"

        # Build a feature-specific system prompt for this request.
        # Re-use the feature key from the first turn if available; re-detect only
        # when the session is new or if the current message clearly signals a new domain.
        detected_key, _ = _detect_feature_key(message)
        if session.feature_key and (not detected_key or detected_key == session.feature_key):
            # No new domain detected, or same domain confirmed → treat as follow-up.
            feature_key = session.feature_key
        else:
            # A different domain was detected (any score ≥ 1) → switch context.
            feature_key = detected_key
        if feature_key and not session.feature_key:
            # First turn with a clear signal → persist for future follow-ups.
            session.feature_key = feature_key
        system_prompt = build_system_prompt(feature_key=feature_key)

        # A fresh session per request keeps state isolated between users.
        # Route knowledge-code to the Pro model for deeper reasoning;
        # fall back to Flash when Pro is not configured.
        use_pro = (
            self._pro_model is not None
            and feature_key == "knowledge-code"
        )
        use_bare = not use_pro and feature_key is None
        active_model = self._pro_model if use_pro else (self._bare_model if use_bare else self._model)
        logger.info("[Model    ] Using %s for feature_key=%s", active_model.model_name, feature_key)

        # Flash model: restrict to feature-scoped tool subset via ToolConfig.allowed_function_names.
        # Pro model skips this — it already uses a scoped tool list from _PRO_TOOLS.
        # No feature_key or unknown key → all tools remain available (safe fallback).
        allowed_names: list[str] | None = None
        if not use_pro and not use_bare and feature_key and feature_key in FLASH_TOOL_SETS:
            allowed_names = sorted(FLASH_TOOL_SETS[feature_key])
            logger.info(
                "[Model    ] Flash tool scoping: feature_key=%s allowed=%d/%d tools",
                feature_key, len(allowed_names), len(ALL_TOOL_FUNCTIONS),
            )

        chat_session = active_model.start_chat(
            enable_automatic_function_calling=False,
            system_instruction=system_prompt,
            feature_key=feature_key,
            allowed_function_names=allowed_names,
            history=history or None,
        )

        # Step 1 — send the user message to Gemini
        logger.info("[Step 1/N] Sending user message to Gemini...")
        t = time.perf_counter()
        response = chat_session.send_message(effective_message)
        first_gemini_elapsed = time.perf_counter() - t
        logger.info("[Step 1/N] Gemini responded  elapsed=%.3fs", first_gemini_elapsed)

        tools_called: list[str] = []
        tool_results_collected: dict[str, Any] = {}  # Collect tool results for context injection in next turn
        tool_params_collected: dict[str, dict] = {}  # Collect tool params for date-range context in next turn
        loop = 0
        gemini_calls = 1  # already made the initial call above
        gemini_elapsed_total = first_gemini_elapsed
        tool_elapsed_total = 0.0
        seen_calls: set[tuple[str, str]] = set()

        # Tool-calling loop — Gemini may request tools before producing a final answer.
        while True:
            loop += 1

            # Collect every function_call part from the current response turn.
            # Must happen BEFORE the MAX_TOOL_LOOPS guard so that a final-text
            # response is never mistaken for a loop-overrun.
            _fc_raw_parts = [
                part
                for part in _response_parts(response)
                if getattr(part, "function_call", None) and part.function_call.name
            ]
            function_calls = [p.function_call for p in _fc_raw_parts]
            # Vertex AI thinking mode requires each FunctionResponse to echo the
            # thought_signature from its matching FunctionCall.  Build a name→sig
            # map now; last-call-wins when the same tool is requested twice.
            _fc_thought_sigs: dict[str, bytes | None] = {
                p.function_call.name: getattr(p, "thought_signature", None)
                for p in _fc_raw_parts
            }

            # No tool calls → Gemini produced the final answer
            if not function_calls:
                elapsed = time.perf_counter() - total_start
                logger.info(
                    "[Step %d  ] Gemini returned final answer  tools_called=%s  gemini_calls=%d  total_elapsed=%.3fs",
                    loop, tools_called, gemini_calls, elapsed,
                )
                break

            if loop > MAX_TOOL_LOOPS:
                logger.warning(
                    "[Step %d  ] Max tool loop reached (%d). gemini_calls=%d total_elapsed=%.3fs. Forcing synthesis.",
                    loop,
                    MAX_TOOL_LOOPS,
                    gemini_calls,
                    time.perf_counter() - total_start,
                )
                _increment_fallback_counter("max_tool_loop")

                # --- Graceful synthesis fallback ---
                # Gemini still wants more tools, but we've gathered enough data.
                # Instead of returning a generic error, ask Gemini to synthesize
                # a final answer from the tool results it already received.
                synthesis_reply = None

                # 1. Check if the current response already contains text alongside tool calls
                partial_text = _sanitize_response(_response_text(response))
                if partial_text and len(partial_text) > 20:
                    synthesis_reply = partial_text
                    logger.info("[Step %d  ] Using partial text from last response (%d chars)", loop, len(partial_text))

                # 2. If no usable text, send a forced-synthesis prompt with actual tool results
                if not synthesis_reply:
                    try:
                        logger.info("[Step %d  ] Sending synthesis prompt to Gemini...", loop)
                        gemini_calls += 1
                        t = time.perf_counter()
                        # Include tool results in synthesis so Gemini has data to synthesize from
                        synth_msg_parts_max: list[str] = [
                            "You have already received enough tool results. Here they are for reference:",
                            json.dumps(tool_results_collected, indent=2, default=str)[:5000],  # Cap at 5k chars
                            "\nDo NOT call any more tools. Answer the user's question NOW using only the data above.",
                            "If some details are uncertain, say so, but still give your best answer.",
                        ]
                        synth_msg_max = "\n\n".join(synth_msg_parts_max)
                        synthesis_response = chat_session.send_message(synth_msg_max)
                        synth_elapsed = time.perf_counter() - t
                        gemini_elapsed_total += synth_elapsed
                        logger.info("[Step %d  ] Synthesis response  elapsed=%.3fs", loop, synth_elapsed)
                        synthesis_reply = _sanitize_response(_response_text(synthesis_response))
                    except Exception as e:
                        logger.warning("[Step %d  ] Synthesis call failed: %s", loop, e)

                total_elapsed = time.perf_counter() - total_start
                reply = synthesis_reply or (
                    "I gathered relevant data but could not fully synthesize an answer. "
                    "Please retry with a more specific query."
                )
                _log_structured_metrics(
                    conversation_id=sid,
                    tools_called=tools_called,
                    gemini_calls=gemini_calls,
                    gemini_latency_seconds=gemini_elapsed_total,
                    tool_latency_seconds=tool_elapsed_total,
                    total_latency_seconds=total_elapsed,
                    fallback_reason="max_tool_loop_synthesized" if synthesis_reply else "max_tool_loop",
                )
                self._record_turn_and_summarize(sid, message, reply, tools_called, tool_results_collected, tool_params_collected)
                return (reply, tools_called, sid)

            logger.info(
                "[Step %d  ] Gemini requested %d tool(s): %s",
                loop, len(function_calls), [fc.name for fc in function_calls],
            )

            # Execute each requested tool and collect the results
            tool_response_parts = []
            steering_notes: list[str] = []  # Steering instructions kept separate from tool result data

            # Deduplicate tool calls — same tool+args won't fire twice in a turn.
            # Track skipped calls so we can send a placeholder function_response for each —
            # Gemini requires response count to equal call count (400 INVALID_ARGUMENT otherwise).
            dedup_calls: list[tuple[str, dict]] = []  # (tool_name, tool_args)
            skipped_names: list[str] = []
            for fc in function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args or {})
                call_key = (tool_name, json.dumps(tool_args, sort_keys=True, default=str))
                if call_key in seen_calls:
                    logger.warning("[Tool     ] skipping duplicate tool call %s(%s)", tool_name, tool_args)
                    skipped_names.append(tool_name)
                    continue
                seen_calls.add(call_key)
                dedup_calls.append((tool_name, tool_args))

            # Phase 1: execute all pending tools (no cache)
            pending_calls: list[tuple[str, dict]] = list(dedup_calls)

            # Phase 2: execute pending tools in parallel when multiple are requested
            def _execute_tool(t_name: str, t_args: dict) -> tuple[str, dict, float]:
                tool_fn = TOOL_REGISTRY.get(t_name)
                if tool_fn is None:
                    raise ValueError(
                        f"LLM requested unknown tool: '{t_name}'. "
                        "This should not happen — check that all tools are registered."
                    )
                t0 = time.perf_counter()
                res = tool_fn(**t_args)
                elapsed = time.perf_counter() - t0
                # Retry once for transient network errors
                if isinstance(res, dict) and res.get("error") == "NETWORK_ERROR":
                    logger.warning("[Tool     ] %s returned NETWORK_ERROR — retrying once", t_name)
                    t0 = time.perf_counter()
                    res = tool_fn(**t_args)
                    elapsed += time.perf_counter() - t0
                return t_name, res, elapsed

            # Results in submission order for deterministic Gemini input
            executed_results: list[tuple[str, dict, dict, float]] = []  # (name, args, result, elapsed)

            if len(pending_calls) > 1:
                # Parallel execution — cap workers to avoid overwhelming external services
                def _execute_tool_in_context(ctx, t_name: str, t_args: dict) -> tuple[str, dict, float]:
                    return ctx.run(_execute_tool, t_name, t_args)

                with ThreadPoolExecutor(max_workers=min(4, len(pending_calls))) as executor:
                    future_to_idx = {
                        executor.submit(_execute_tool_in_context, copy_context(), tn, ta): i
                        for i, (tn, ta) in enumerate(pending_calls)
                    }
                    result_by_idx: dict[int, tuple[str, dict, dict, float]] = {}
                    for future in as_completed(future_to_idx):
                        idx = future_to_idx[future]
                        tn, ta = pending_calls[idx]
                        res_name, res_data, res_elapsed = future.result()
                        result_by_idx[idx] = (res_name, ta, res_data, res_elapsed)
                    # Preserve original order
                    for i in range(len(pending_calls)):
                        executed_results.append(result_by_idx[i])
            elif len(pending_calls) == 1:
                tn, ta = pending_calls[0]
                logger.info("[Tool     ] → %s(%s)", tn, ta)
                res_name, res_data, res_elapsed = _execute_tool(tn, ta)
                executed_results.append((res_name, ta, res_data, res_elapsed))

            # Phase 3: post-process results (annotation)
            for tool_name, tool_args, result, tool_elapsed in executed_results:
                tool_elapsed_total += tool_elapsed
                logger.info(
                    "[Tool     ] ← %s  elapsed=%.3fs  result_keys=%s",
                    tool_name,
                    tool_elapsed,
                    list(result.keys()) if isinstance(result, dict) else type(result).__name__,
                )

                # Annotate search_organizations results so Gemini lists matching
                # candidates with IDs instead of giving a generic "no match" response.
                if tool_name == "search_organizations" and isinstance(result, dict):
                    orgs = result.get("organizations", [])
                    if isinstance(orgs, list) and orgs:
                        org_labels = []
                        org_ids = []
                        for o in orgs[:10]:
                            if isinstance(o, dict):
                                oname = o.get("organizationName") or o.get("name") or o.get("기업명") or o.get("기업") or ""
                                oid = o.get("organizationId") or o.get("id") or o.get("기업ID") or o.get("기업코드") or ""
                                if oname:
                                    org_labels.append(f"{oname} (id:{oid})")
                                    org_ids.append(str(oid))
                        if len(org_labels) == 1:
                            steering_notes.append(
                                f"Exactly ONE org match: {org_labels[0]}. "
                                "Use this organization's ID in your next tool call. "
                                "Do NOT ask the user to confirm. Do NOT output text first."
                            )
                        elif len(org_labels) > 1:
                            steering_notes.append(
                                f"Multiple organizations match the query. Found: {', '.join(org_labels)}. "
                                "You MUST list these candidates to the user with their names and IDs, "
                                "and ask which one they mean. Do NOT pick one on their behalf."
                            )
                    elif isinstance(orgs, list) and len(orgs) == 0:
                        steering_notes.append(
                            "No organizations matched the search query. "
                            "Tell the user no match was found and suggest they check the org name or try a different search term."
                        )

                # Steer away from redundant get_orders_admin_panel retries within the same turn.
                if tool_name == "get_orders_admin_panel" and tool_name in tools_called:
                    steering_notes.append(
                        "You already called get_orders_admin_panel earlier this turn. "
                        "Do NOT call it again with different date or sort params. "
                        "Synthesize the final answer from the results already returned above."
                    )

                tools_called.append(tool_name)
                # Collect result and params for context injection in next turn
                if tool_name not in tool_results_collected:
                    tool_results_collected[tool_name] = result
                if tool_name not in tool_params_collected:
                    tool_params_collected[tool_name] = tool_args
                # Note: if same tool is called multiple times in one turn, we keep first result
                # (usually sufficient for context, and avoids token bloat from repeated data)

                _tsig = _fc_thought_sigs.get(tool_name)
                _fn_resp_kwargs: dict[str, Any] = {
                    "function_response": types.FunctionResponse(
                        name=tool_name,
                        response={"result": json.dumps(result, default=str)},
                    ),
                }
                if _tsig is not None:
                    _fn_resp_kwargs["thought_signature"] = _tsig
                tool_response_parts.append(types.Part(**_fn_resp_kwargs))

            # Gemini requires one function_response per function_call in the turn.
            # Send placeholder responses for calls that were skipped (dedup / scope guard)
            # so the response count always matches the call count.
            # Include thought_signature in stubs too — Vertex AI validates every response.
            for skipped_name in skipped_names:
                _tsig = _fc_thought_sigs.get(skipped_name)
                _skip_kwargs: dict[str, Any] = {
                    "function_response": types.FunctionResponse(
                        name=skipped_name,
                        response={"result": json.dumps({"note": "duplicate call — prior result applies"}, default=str)},
                    ),
                }
                if _tsig is not None:
                    _skip_kwargs["thought_signature"] = _tsig
                tool_response_parts.append(types.Part(**_skip_kwargs))

            # Append steering instructions as a dedicated text Part — clearly separate
            # from tool result data so the LLM reads them as directives, not as data.
            # Deduplicate identical steering notes (e.g. parallel tools may produce the
            # same instruction).
            if steering_notes and tool_response_parts:
                seen: set[str] = set()
                unique_notes: list[str] = []
                for note in steering_notes:
                    if note not in seen:
                        seen.add(note)
                        unique_notes.append(note)
                tool_response_parts.append(
                    types.Part.from_text(text="\n\n".join(unique_notes))
                )

            if not tool_response_parts:
                logger.warning("[Step %d  ] No new tool results to send. Returning early.", loop)
                reply = (
                    "I could not complete the answer because tool calls became repetitive. "
                    "Please retry with a narrower question."
                )
                _increment_fallback_counter("repetitive_tool_calls")
                total_elapsed = time.perf_counter() - total_start
                _log_structured_metrics(
                    conversation_id=sid,
                    tools_called=tools_called,
                    gemini_calls=gemini_calls,
                    gemini_latency_seconds=gemini_elapsed_total,
                    tool_latency_seconds=tool_elapsed_total,
                    total_latency_seconds=total_elapsed,
                    fallback_reason="repetitive_tool_calls",
                )
                self._record_turn_and_summarize(sid, message, reply, tools_called, tool_params=tool_params_collected)
                return (reply, tools_called, sid)

            # Send all tool results back to Gemini in one message
            gemini_calls += 1
            n_tool_results = len([p for p in tool_response_parts if not p.text])
            logger.info(
                "[Step %d  ] Sending %d tool result(s)%s back to Gemini...  (gemini_calls so far: %d/%d)",
                loop, n_tool_results, f" + {len(steering_notes)} steering note(s)" if steering_notes else "",
                gemini_calls, MAX_TOOL_LOOPS + 1,
            )
            t = time.perf_counter()
            response = chat_session.send_message(tool_response_parts)
            gemini_elapsed = time.perf_counter() - t
            gemini_elapsed_total += gemini_elapsed
            logger.info("[Step %d  ] Gemini responded  elapsed=%.3fs", loop, gemini_elapsed)

        reply = _sanitize_response(_response_text(response))
        if not reply:
            # The thinking model produced only thought-parts with no visible text.
            # Send one forced-synthesis prompt to get a proper answer, and include
            # the actual tool results so Gemini has the data to synthesize from.
            logger.warning(
                "[Reply    ] Empty reply after sanitization (likely all-thought response). "
                "Sending synthesis prompt..."
            )
            try:
                gemini_calls += 1
                t = time.perf_counter()
                # Build synthesis message with tool results
                synth_msg_parts: list[str] = [
                    "Here are your tool results. Please write your final answer NOW using this data:",
                    json.dumps(tool_results_collected, indent=2, default=str)[:5000],  # Cap at 5k chars
                    "\nDo NOT call any more tools. Provide a clear, concise response for the admin.",
                ]
                synth_msg = "\n\n".join(synth_msg_parts)
                synth_response = chat_session.send_message(synth_msg)
                synth_elapsed = time.perf_counter() - t
                gemini_elapsed_total += synth_elapsed
                logger.info("[Reply    ] Synthesis response  elapsed=%.3fs", synth_elapsed)
                reply = _sanitize_response(_response_text(synth_response))
            except Exception as exc:
                logger.warning("[Reply    ] Synthesis call failed: %s", exc)
            if not reply:
                logger.warning("[Reply    ] Still empty after synthesis — returning error fallback.")
                reply = (
                    "I processed your request but was unable to generate a response. "
                    "Please try again."
                )

        total_elapsed = time.perf_counter() - total_start
        _log_structured_metrics(
            conversation_id=sid,
            tools_called=tools_called,
            gemini_calls=gemini_calls,
            gemini_latency_seconds=gemini_elapsed_total,
            tool_latency_seconds=tool_elapsed_total,
            total_latency_seconds=total_elapsed,
            fallback_reason=None,
        )
        self._record_turn_and_summarize(sid, message, reply, tools_called, tool_results_collected, tool_params_collected)
        return (reply, tools_called, sid)

    # -- Memory integration helpers ------------------------------------------

    def _record_turn_and_summarize(
        self,
        session_id: str,
        user_message: str,
        assistant_reply: str,
        tools_called: list[str],
        tool_results: dict[str, Any] | None = None,
        tool_params: dict[str, dict] | None = None,
    ) -> None:
        """Record user + assistant turns, extract entities, and trigger summarization."""
        self._memory.add_turn(
            session_id, role="user", content=user_message,
        )
        self._memory.add_turn(
            session_id,
            role="assistant",
            content=assistant_reply,
            tools_called=tools_called,
            tool_results=tool_results,
            tool_params=tool_params,
        )

        # Auto-extract entities from assistant reply
        self._memory.extract_and_store_entities(session_id, assistant_reply)

        # Summarize synchronously to avoid race conditions where a subsequent
        # message arrives before the summary is applied, causing stale context.
        if self._memory.needs_summarization(session_id):
            session = self._memory.get_session(session_id)
            if session:
                from app.orchestrator.memory_service import SHORT_TERM_MAX_TURNS
                older_turns = session.turns[:-SHORT_TERM_MAX_TURNS] if len(session.turns) > SHORT_TERM_MAX_TURNS else []
                # Skip trivial summaries — wait until there's enough to compress
                if len(older_turns) >= 2 and self._memory.begin_summarization(session_id):
                    existing_summary = session.summary
                    logger.info(
                        "[Memory] Running synchronous summarization of %d older turns for session %s",
                        len(older_turns), session_id,
                    )
                    try:
                        new_summary = summarize_conversation(list(older_turns), existing_summary)
                        self._memory.apply_summary(session_id, new_summary)
                    except Exception:
                        logger.exception("[Memory] Summarization failed for session %s", session_id)
                    finally:
                        self._memory.end_summarization(session_id)
