import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from datetime import date
from typing import Any

from google.genai import types

from app.config import settings
from app.llm.gemini_client import create_gemini_model
from app.orchestrator.context_builder import build_context
from app.orchestrator.context_store import ConversationState
from app.orchestrator.memory_service import MemoryService
from app.orchestrator.summarizer import summarize_conversation
from app.prompts.builder import build_system_prompt
from app.tools import ALL_TOOL_FUNCTIONS, TOOL_REGISTRY

logger = logging.getLogger(__name__)
MAX_TOOL_LOOPS = 3      # max Gemini round-trips in tool loop → caps total Gemini calls at MAX_TOOL_LOOPS+1
# Accept explicit ORD-* IDs or numeric IDs only.
# Prevent false positives like organization names (e.g. "DHLSC").
ORDER_ID_PATTERN = re.compile(r"\b(?:ORD-[A-Za-z0-9-]{3,}|\d{5,})\b", re.IGNORECASE)

_fallback_counters = {
    "max_tool_loop": 0,
    "repetitive_tool_calls": 0,
}
_fallback_counter_lock = threading.Lock()
# Markers we inject ourselves; strip them from user input to prevent prompt injection.
_INJECTION_PATTERN = re.compile(r"\[\s*(?:Instruction|Today's date)\s*:", re.IGNORECASE)


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
    """Extract plain text response with a safe fallback."""
    if response.text:
        return response.text
    texts: list[str] = []
    for part in _response_parts(response):
        if part.text:
            texts.append(part.text)
    return "\n".join(texts).strip()


def _trim_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


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


def _extract_order_id_candidates(message: str) -> list[str]:
    found = [_normalize_order_id(m.group(0)) for m in ORDER_ID_PATTERN.finditer(message)]
    unique: list[str] = []
    seen: set[str] = set()
    for oid in found:
        if not oid:
            continue
        if oid in seen:
            continue
        seen.add(oid)
        unique.append(oid)
    return unique


def _extract_context_hints(tool_results: dict[str, Any]) -> str:
    """Extract useful context from previous tool results (report data, orders, etc.)."""
    if not tool_results:
        return ""

    hints: list[str] = []

    # Extract organization names + IDs from report results (for follow-up context)
    for rpt_name in (
        "get_statement_of_use_summary", "get_statement_of_use_detail",
        "get_statement_of_use_driver_summary", "get_statement_of_use_driver_detail",
    ):
        report_data = tool_results.get(rpt_name)
        if not isinstance(report_data, dict):
            continue
        rows = report_data.get("rows", [])
        if not isinstance(rows, list):
            continue
        org_entries: list[str] = []
        for row in rows[:5]:  # First 5 orgs
            if isinstance(row, dict):
                name = row.get("organizationName") or ""
                oid = row.get("organizationId") or ""
                if name and isinstance(name, str):
                    label = f"{name} (id:{oid})" if oid else name
                    if label not in org_entries:
                        org_entries.append(label)
        if org_entries:
            hints.append(f"Organizations in report: {', '.join(org_entries)}")

    # Extract user profile data (for cross-turn reference reuse)
    for usr_name in ("get_user_profile", "search_users"):
        user_data = tool_results.get(usr_name)
        if not isinstance(user_data, dict):
            continue
        uid = user_data.get("userId") or user_data.get("id")
        uname = user_data.get("name") or user_data.get("userName")
        if uid:
            label = f"{uname} (id:{uid})" if uname else f"id:{uid}"
            hints.append(f"User in context: {label}")

    return "\n".join(hints) if hints else ""


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


_REPORT_INTENT_KEYWORDS = (
    # English
    "statement",
    "report",
    "revenue",
    "summary",
    # Korean
    "통계",
    "보고서",
    "매출",
    "요약",
    "1 week",
    "this week",
    "this month",
)
_REPORT_TOOL_NAMES = {
    "get_statement_of_use_summary",
    "get_statement_of_use_detail",
    "get_statement_of_use_driver_summary",
    "get_statement_of_use_driver_detail",
    "get_b2b_tracking_service_detail",
}

_DATE_TOKEN_PATTERN = re.compile(r"\b(?:\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
# Matches "7 days", "7일", "2 weeks", "3 months", "2주", "3달" etc. (English and Korean only)
_NUMERIC_PERIOD_PATTERN = re.compile(
    r"\b\d+\s*(?:day|days|week|weeks|month|months|일|주|달|개월)\b",
    re.IGNORECASE,
)
_RELATIVE_DATE_KEYWORDS = (
    "today",
    "yesterday",
    "this week",
    "last week",
    "this month",
    "last month",
    "this year",
    "last year",
    "week",
    "month",
    "year",
    # Korean
    "오늘",
    "어제",
    "이번 주",
    "지난 주",
    "이번 달",
    "지난 달",
    "이번 년",
)


_DETAIL_INTENT_KEYWORDS = (
    # English
    "detail",
    "order id",
    "orderid",
    "per order",
    "list order",
    "list orders",
    # Korean
    "상세",
    "주문 목록",
    "주문 id",
    "건별",
)

_SUMMARY_TOOL_NAMES = {
    "get_statement_of_use_summary",
    "get_statement_of_use_driver_summary",
}

# ---------------------------------------------------------------------------
# Feature detection — keyword-based routing for modular prompt composition.
# Maps each feature domain to keywords (English + Korean).
# ---------------------------------------------------------------------------
_FEATURE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "report-summary": (
        "statement", "report", "revenue", "통계", "보고서", "매출", "요약",
    ),
    "order-lookup": (
        "order", "delivery", "coupon", "cancel fee", "reorder", "shipping record",
        "price estimate", "pricing", "주문", "배달", "배송", "쿠폰", "취소",
    ),
    "driver-tracking": (
        "driver", "route", "tracking", "기사", "운전", "배차",
    ),
    "user-admin": (
        "user profile", "organization", "branch", "admin role", "permission",
        "feature flag", "department", "사용자", "조직", "지점", "권한",
    ),
    "common-data": (
        "vehicle pool", "vehicle service", "vehicle prices", "address search",
        "home moving", "ads", "common service", "차량", "차종", "주소", "이사",
    ),
    "knowledge-code": (
        "enum", "status code", "struct", "handler", "service flow",
        "endpoint", "codebase", "api consumer", "graph",
    ),
}


def _detect_feature_key(message: str) -> str | None:
    """Detect the most likely feature domain from the user's message.

    Simple keyword scoring — no LLM call. Returns None when no clear match.
    """
    lower = (message or "").lower()
    if not lower:
        return None

    best_key: str | None = None
    best_score = 0
    for feature, keywords in _FEATURE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > best_score:
            best_score = score
            best_key = feature

    return best_key


def _looks_like_report_query(message: str) -> bool:
    normalized = (message or "").lower().strip()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in _REPORT_INTENT_KEYWORDS)


def _wants_detail_level(message: str) -> bool:
    """True when the user's message implies order-level / per-row detail."""
    normalized = (message or "").lower().strip()
    if not normalized:
        return False
    return any(kw in normalized for kw in _DETAIL_INTENT_KEYWORDS)


def _message_has_explicit_date_intent(message: str) -> bool:
    """True when the current user message explicitly specifies a date/time filter."""
    normalized = (message or "").lower().strip()
    if not normalized:
        return False

    if _DATE_TOKEN_PATTERN.search(normalized):
        return True

    if _NUMERIC_PERIOD_PATTERN.search(normalized):
        return True

    return any(keyword in normalized for keyword in _RELATIVE_DATE_KEYWORDS)


def _sanitize_report_tool_args(tool_name: str, tool_args: dict[str, Any], message: str) -> dict[str, Any]:
    """Drop stale date args for report tools when the user did not specify any date in this turn.

    This prevents Gemini from carrying old date ranges from prior context and
    lets the service client apply dynamic defaults (last 3 days from today).
    """
    if tool_name not in _REPORT_TOOL_NAMES:
        return tool_args
    if _message_has_explicit_date_intent(message):
        return tool_args

    sanitized = dict(tool_args)
    for key in ("from_date", "to_date", "fromDate", "toDate"):
        sanitized.pop(key, None)
    return sanitized


def _build_report_note(
    rows: list[dict],
    tool_name: str,
    *,
    user_wants_detail: bool = False,
    org_search_results: dict | None = None,
    tool_had_org_filter: bool = False,
    detail_tool_already_called: bool = False,
) -> str:
    """Build a smart _note for report tool results.

    Extracts distinct organization names and flags potential ambiguity
    (e.g. orgs sharing a common prefix) so Gemini can apply entity
    resolution instead of guessing.

    When a summary tool was called but the user asked for detail-level
    data, injects a corrective instruction telling Gemini to call the
    detail variant — UNLESS the detail tool was already called in the
    same batch.

    When search_organizations was already called but the report tool
    was called without organization_id, reminds Gemini to answer from
    the rows it already has (client-side filter by org name).
    """
    if not rows:
        return "Report returned no rows for this filter/date range."

    # Collect distinct orgs from the result set.
    org_entries: dict[str, str] = {}  # orgName -> orgId
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("organizationName") or ""
        oid = str(row.get("organizationId") or "")
        if name and name not in org_entries:
            org_entries[name] = oid

    # If summary was called but user wanted detail, inject corrective note.
    # UNLESS the detail tool was already called in this batch (prevents duplicate requests).
    is_summary_tool = tool_name in _SUMMARY_TOOL_NAMES
    if is_summary_tool and user_wants_detail and not detail_tool_already_called:
        detail_tool = tool_name.replace("_summary", "_detail")
        return (
            f"WARNING: You called {tool_name} (summary) but the user is asking for "
            "detail-level data (order IDs, per-order payment, etc.). "
            "Summary rows do NOT contain orderId or per-order fields. "
            f"You MUST now call {detail_tool} with the same date/pay params "
            "to get order-level rows. Do NOT answer from summary data alone."
        )
    
    # If summary tool was called AND the detail variant was already called/collected,
    # remind Gemini that detail data is available and should NOT be called again.
    if is_summary_tool and detail_tool_already_called:
        return (
            "Both summary and detail results are now available. "
            "Use the detail rows (which contain orderId, paymentMethod, etc.) "
            "to answer questions about individual orders. "
            "Do NOT call the detail tool again — use the data you already have."
        )

    parts = [
        "Answer from these rows ONLY. Apply entity-resolution and answer-grounding rules.",
    ]

    # If search_organizations was called but report was not filtered by org_id,
    # instruct Gemini to filter the rows client-side instead of re-calling.
    if org_search_results and not tool_had_org_filter:
        searched_orgs = org_search_results.get("organizations", [])
        if isinstance(searched_orgs, list) and searched_orgs:
            org_hints = []
            for o in searched_orgs[:5]:
                if isinstance(o, dict):
                    oname = o.get("organizationName") or o.get("name") or ""
                    oid = o.get("organizationId") or o.get("id") or ""
                    if oname:
                        org_hints.append(f"{oname} (id:{oid})")
            if org_hints:
                parts.append(
                    "IMPORTANT: You already searched for organizations and found: "
                    + ", ".join(org_hints)
                    + ". The report data above contains ALL organizations. "
                    "Filter rows by matching organizationName or organizationId to the user's query. "
                    "Do NOT re-call this report tool — answer from these rows now."
                )

    if org_entries:
        # Detect groups of similar names using multiple strategies:
        # 1. Shared prefix (>=3 chars)
        # 2. Case-insensitive substring containment
        names = sorted(org_entries.keys())
        similar_groups: list[list[str]] = []
        used: set[str] = set()
        for i, a in enumerate(names):
            if a in used:
                continue
            group = [a]
            a_lower = a.lower()
            prefix_a = a_lower[:3]
            for b in names[i + 1:]:
                if b in used:
                    continue
                b_lower = b.lower()
                # Match on shared prefix OR one name is a substring of the other
                if b_lower[:3] == prefix_a or a_lower in b_lower or b_lower in a_lower:
                    group.append(b)
            if len(group) > 1:
                similar_groups.append(group)
                used.update(group)

        org_list = ", ".join(f"{n} (id:{org_entries[n]})" for n in names[:15])
        parts.append(f"Distinct organizations in result: {org_list}.")

        if similar_groups:
            warnings = []
            for grp in similar_groups:
                items = " vs ".join(f'"{n}" (id:{org_entries[n]})' for n in grp)
                warnings.append(items)
            parts.append(
                "AMBIGUITY WARNING — similar organization names detected: "
                + "; ".join(warnings)
                + ". These are DIFFERENT entities. Try exact match first, then case-insensitive match. "
                "If user query does not match exactly one name, list all candidates and ask user to clarify."
            )

    return " ".join(parts)


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
        # Build the model once at startup — it holds the tool schema and
        # system prompt, so it is safe to reuse across requests.
        logger.info("[Orchestrator] Loading Gemini model with %d tools...", len(ALL_TOOL_FUNCTIONS))
        self._model = create_gemini_model(ALL_TOOL_FUNCTIONS)

        store = None
        if settings.chat_history_db:
            from app.persistence.chat_store import ChatStore
            store = ChatStore(settings.chat_history_db)

        self._memory = MemoryService(store=store)
        logger.info("[Orchestrator] Gemini model ready.")

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

        # Build context using hybrid memory (summary + long-term + recent turns)
        effective_message = build_context(sid, safe_message, self._memory)
        # Always inject today's date so Gemini can compute relative periods ("last 7 days", etc.)
        effective_message = f"[Today's date: {date.today().isoformat()}]\n\n{effective_message}"

        # Build a feature-specific system prompt for this request.
        feature_key = _detect_feature_key(message)
        system_prompt = build_system_prompt(feature_key=feature_key)

        # For report queries: inject a direct tool instruction into the user message.
        # This prevents the costly pattern of: Gemini answers text → retry call → lookup_enum call → report call.
        # By hinting upfront, Gemini calls the right report tool on the very first try.
        if feature_key == "report-summary":
            if _wants_detail_level(message):
                effective_message += (
                    "\n\n[Instruction: Call get_statement_of_use_detail immediately. "
                    "pay values: cash, credit, card, point, brandpay — omit pay to include all types. "
                    "Do not call lookup_enum or any other tool first.]"
                )
            else:
                effective_message += (
                    "\n\n[Instruction: Call get_statement_of_use_summary immediately. "
                    "pay values: cash, credit, card, point, brandpay — omit pay to include all types. "
                    "Do not call lookup_enum or any other tool first.]"
                )

        # A fresh session per request keeps state isolated between users.
        chat_session = self._model.start_chat(
            enable_automatic_function_calling=False,
            system_instruction=system_prompt,
            feature_key=feature_key,
        )

        # Step 1 — send the user message to Gemini
        logger.info("[Step 1/N] Sending user message to Gemini...")
        t = time.perf_counter()
        response = chat_session.send_message(effective_message)
        first_gemini_elapsed = time.perf_counter() - t
        logger.info("[Step 1/N] Gemini responded  elapsed=%.3fs", first_gemini_elapsed)

        tools_called: list[str] = []
        tool_results_collected: dict[str, Any] = {}  # Collect tool results for context injection in next turn
        loop = 0
        gemini_calls = 1  # already made the initial call above
        gemini_elapsed_total = first_gemini_elapsed
        tool_elapsed_total = 0.0
        seen_calls: set[tuple[str, str]] = set()
        # If Gemini tries to answer a report query without tools on the first pass,
        # force one retry that explicitly asks for a report tool call.
        report_tool_retry_used = False

        # Tool-calling loop — Gemini may request tools before producing a final answer.
        while True:
            loop += 1

            # Collect every function_call part from the current response turn.
            # Must happen BEFORE the MAX_TOOL_LOOPS guard so that a final-text
            # response is never mistaken for a loop-overrun.
            function_calls = [
                part.function_call
                for part in _response_parts(response)
                if getattr(part, "function_call", None) and part.function_call.name
            ]

            # No tool calls → Gemini produced the final answer
            if not function_calls:
                if (
                    not tools_called
                    and loop == 1
                    and not report_tool_retry_used
                    and _looks_like_report_query(message)
                ):
                    report_tool_retry_used = True
                    logger.warning(
                        "[Step %d  ] Report-like query answered without tools on first pass. Forcing one tool-call retry.",
                        loop,
                    )
                    gemini_calls += 1
                    t = time.perf_counter()
                    if _wants_detail_level(message):
                        retry_msg = (
                            "This is a detail-level report query. Call get_statement_of_use_detail IMMEDIATELY "
                            "(NOT summary, NOT lookup_enum, NOT any other tool first). "
                            "Valid pay values: cash, credit, card, point, brandpay — use directly, do not look them up. "
                            "Omit pay to include all types."
                        )
                    else:
                        retry_msg = (
                            "This is a report query. Call get_statement_of_use_summary IMMEDIATELY. "
                            "Do NOT call lookup_enum, search_codebase, or any other tool first. "
                            "Valid pay values: cash, credit, card, point, brandpay — use directly, do not look them up. "
                            "Omit pay to include all types. Do not answer from memory."
                        )
                    response = chat_session.send_message(retry_msg)
                    gemini_elapsed = time.perf_counter() - t
                    gemini_elapsed_total += gemini_elapsed
                    logger.info("[Step %d  ] Gemini retry response  elapsed=%.3fs", loop, gemini_elapsed)
                    continue

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
                partial_text = _response_text(response)
                if partial_text and len(partial_text) > 20:
                    synthesis_reply = partial_text
                    logger.info("[Step %d  ] Using partial text from last response (%d chars)", loop, len(partial_text))

                # 2. If no usable text, send a forced-synthesis prompt
                if not synthesis_reply:
                    try:
                        logger.info("[Step %d  ] Sending synthesis prompt to Gemini...", loop)
                        gemini_calls += 1
                        t = time.perf_counter()
                        synthesis_response = chat_session.send_message(
                            "You have already received enough tool results. "
                            "Do NOT call any more tools. Answer the user's question NOW "
                            "using only the data from your previous tool calls. "
                            "If some details are uncertain, say so, but still give your best answer."
                        )
                        synth_elapsed = time.perf_counter() - t
                        gemini_elapsed_total += synth_elapsed
                        logger.info("[Step %d  ] Synthesis response  elapsed=%.3fs", loop, synth_elapsed)
                        synthesis_reply = _response_text(synthesis_response)
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
                self._record_turn_and_summarize(sid, message, reply, tools_called, tool_results_collected)
                return (reply, tools_called, sid)

            logger.info(
                "[Step %d  ] Gemini requested %d tool(s): %s",
                loop, len(function_calls), [fc.name for fc in function_calls],
            )

            # Execute each requested tool and collect the results
            tool_response_parts = []
            steering_notes: list[str] = []  # Steering instructions kept separate from tool result data

            # Separate tool calls into cache-servable, parallel-eligible, and deferred
            dedup_calls: list[tuple[str, dict]] = []  # (tool_name, tool_args)
            for fc in function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args or {})
                tool_args = _sanitize_report_tool_args(tool_name, tool_args, message)
                call_key = (tool_name, json.dumps(tool_args, sort_keys=True, default=str))
                if call_key in seen_calls:
                    logger.warning("[Tool     ] skipping duplicate tool call %s(%s)", tool_name, tool_args)
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
                        for o in orgs[:10]:
                            if isinstance(o, dict):
                                oname = o.get("organizationName") or o.get("name") or ""
                                oid = o.get("organizationId") or o.get("id") or ""
                                if oname:
                                    org_labels.append(f"{oname} (id:{oid})")
                        if len(org_labels) == 1:
                            steering_notes.append(
                                f"Exactly ONE match found: {org_labels[0]}. "
                                "Proceed to call the report tool with this organization_id. "
                                "Do NOT ask the user to confirm when there is only one match."
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

                if tool_name in _REPORT_TOOL_NAMES and isinstance(result, dict):
                    rows = result.get("rows")
                    has_rows = isinstance(rows, list) and len(rows) > 0
                    # Check if search_organizations was already called in this turn
                    org_search_res = tool_results_collected.get("search_organizations")
                    had_org_filter = bool(tool_args.get("organization_id") or tool_args.get("orgId"))
                    # Check if the detail variant of this tool was already called in this batch
                    detail_called = False
                    if tool_name in _SUMMARY_TOOL_NAMES:
                        detail_tool_name = tool_name.replace("_summary", "_detail")
                        detail_called = detail_tool_name in tool_results_collected
                    note = _build_report_note(
                        rows if has_rows else [],
                        tool_name,
                        user_wants_detail=_wants_detail_level(message),
                        org_search_results=org_search_res,
                        tool_had_org_filter=had_org_filter,
                        detail_tool_already_called=detail_called,
                    )
                    if note:
                        steering_notes.append(note)

                tools_called.append(tool_name)
                # Collect result for context injection in next turn
                if tool_name not in tool_results_collected:
                    tool_results_collected[tool_name] = result
                # Note: if same tool is called multiple times in one turn, we keep first result
                # (usually sufficient for context, and avoids token bloat from repeated data)

                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": json.dumps(result, default=str)},
                    )
                )

            # Append steering instructions as a dedicated text Part — clearly separate
            # from tool result data so the LLM reads them as directives, not as data.
            if steering_notes and tool_response_parts:
                tool_response_parts.append(
                    types.Part.from_text(text="\n\n".join(steering_notes))
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
                self._record_turn_and_summarize(sid, message, reply, tools_called)
                return (reply, tools_called, sid)

            # Send all tool results back to Gemini in one message
            gemini_calls += 1
            logger.info(
                "[Step %d  ] Sending %d tool result(s) back to Gemini...  (gemini_calls so far: %d/%d)",
                loop, len(tool_response_parts), gemini_calls, MAX_TOOL_LOOPS + 1,
            )
            t = time.perf_counter()
            response = chat_session.send_message(tool_response_parts)
            gemini_elapsed = time.perf_counter() - t
            gemini_elapsed_total += gemini_elapsed
            logger.info("[Step %d  ] Gemini responded  elapsed=%.3fs", loop, gemini_elapsed)

        reply = _response_text(response)

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
        self._record_turn_and_summarize(sid, message, reply, tools_called, tool_results_collected)
        return (reply, tools_called, sid)

    # -- Memory integration helpers ------------------------------------------

    def _record_turn_and_summarize(
        self,
        session_id: str,
        user_message: str,
        assistant_reply: str,
        tools_called: list[str],
        tool_results: dict[str, Any] | None = None,
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
        )

        # Auto-extract entities from assistant reply
        self._memory.extract_and_store_entities(session_id, assistant_reply)

        # Summarize in background if threshold reached (avoid blocking response)
        if self._memory.needs_summarization(session_id):
            session = self._memory.get_session(session_id)
            if session:
                from app.orchestrator.memory_service import SHORT_TERM_MAX_TURNS
                older_turns = session.turns[:-SHORT_TERM_MAX_TURNS] if len(session.turns) > SHORT_TERM_MAX_TURNS else []
                # Skip trivial summaries — wait until there's enough to compress
                if len(older_turns) >= 2 and self._memory.begin_summarization(session_id):
                    existing_summary = session.summary
                    logger.info(
                        "[Memory] Scheduling background summarization of %d older turns for session %s",
                        len(older_turns), session_id,
                    )
                    thread = threading.Thread(
                        target=self._summarize_background,
                        args=(session_id, list(older_turns), existing_summary),
                        daemon=True,
                    )
                    thread.start()

    def _summarize_background(
        self,
        session_id: str,
        older_turns: list,
        existing_summary: str,
    ) -> None:
        """Run summarization off the critical path."""
        try:
            new_summary = summarize_conversation(older_turns, existing_summary)
            self._memory.apply_summary(session_id, new_summary)
        except Exception:
            logger.exception("[Memory] Background summarization failed for session %s", session_id)
        finally:
            self._memory.end_summarization(session_id)
