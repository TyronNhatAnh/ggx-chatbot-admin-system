"""
Hybrid conversation memory system.

Three layers:
1. Short-term memory  — last N turns, always in LLM context.
2. Summary memory     — compressed history replacing older turns.
3. Long-term memory   — retrievable facts/entities/decisions stored separately.
"""

import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.persistence.chat_store import ChatStore


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SHORT_TERM_MAX_TURNS = 5           # recent turns kept verbatim
SUMMARIZE_THRESHOLD = 5            # summarize after this many new turns since last summary
LONG_TERM_MAX_ITEMS = 50           # cap per session
TOOL_RESULT_SUMMARY_LIMIT = 300    # chars — truncate large tool payloads before storage
SESSION_TTL_SECONDS = 1800         # 30 min inactivity → expire

# Entity patterns for automatic extraction
_ENTITY_PATTERNS: dict[str, re.Pattern[str]] = {
    "orderId": re.compile(r"\b(?:ORD-[A-Za-z0-9\-]{3,}|\d{5,})\b"),
    "userId": re.compile(r"\buser[_\-]?(?:id)?[:\s]+([A-Za-z0-9\-]+)", re.IGNORECASE),
    "driverId": re.compile(r"\bdriver[_\-]?(?:id)?[:\s]+([A-Za-z0-9\-]+)", re.IGNORECASE),
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
class MemoryType(str, Enum):
    FACT = "fact"
    ENTITY = "entity"
    DECISION = "decision"


@dataclass
class MemoryItem:
    id: str
    type: MemoryType
    content: str
    created_at: float = field(default_factory=time.time)


@dataclass
class Turn:
    """One conversation turn (user ↔ assistant exchange)."""
    role: str                               # "user" | "assistant" | "tool"
    content: str
    tools_called: list[str] = field(default_factory=list)
    tool_results: dict[str, Any] = field(default_factory=dict)
    tool_params: dict[str, dict] = field(default_factory=dict)  # params used per tool call (for date-range context)
    created_at: float = field(default_factory=time.time)


@dataclass
class SessionState:
    """Complete memory state for one conversation session."""
    session_id: str
    # All turns since session start (rotated after summarization)
    turns: list[Turn] = field(default_factory=list)
    # Running summary of older conversation
    summary: str = ""
    # Long-term memory items
    memory: list[MemoryItem] = field(default_factory=list)
    # Turns added since last summarization
    turns_since_summary: int = 0
    # Guard against concurrent background summarization threads
    summarization_in_progress: bool = False
    # Detected feature key from the first turn — persists across follow-ups
    feature_key: str | None = None
    # Report scope from prior turn ("customer", "driver", or "both") — persists for follow-up detail requests
    report_scope: str | None = None
    # Housekeeping
    updated_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Memory service
# ---------------------------------------------------------------------------
class MemoryService:
    """Thread-safe in-memory session store with three memory layers.

    Pass a ``ChatStore`` instance via ``store=`` to persist sessions to SQLite
    so that conversation history survives server restarts.
    """

    def __init__(
        self,
        *,
        short_term_max: int = SHORT_TERM_MAX_TURNS,
        summarize_threshold: int = SUMMARIZE_THRESHOLD,
        long_term_max: int = LONG_TERM_MAX_ITEMS,
        ttl_seconds: int = SESSION_TTL_SECONDS,
        store: "ChatStore | None" = None,
    ) -> None:
        self._short_term_max = short_term_max
        self._summarize_threshold = summarize_threshold
        self._long_term_max = long_term_max
        self._ttl_seconds = ttl_seconds
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.Lock()
        self._store = store

    # -- session lifecycle ---------------------------------------------------

    def get_or_create(self, session_id: str | None) -> SessionState:
        with self._lock:
            _expired = self._purge_expired()
            sid = (session_id or "").strip()
            if sid and sid in self._sessions:
                state = self._sessions[sid]
                state.updated_at = time.time()
                _result = state
            else:
                new_id = sid or str(uuid.uuid4())
                # Try to restore from persistent store before creating a blank session
                if new_id and self._store is not None:
                    persisted = self._store.load_session(new_id)
                    if persisted is not None:
                        self._sessions[new_id] = persisted
                        persisted.updated_at = time.time()
                        _result = persisted
                    else:
                        _result = None
                else:
                    _result = None
                if _result is None:
                    _result = SessionState(session_id=new_id)
                    self._sessions[new_id] = _result
                    if self._store is not None:
                        self._store.save_session_meta(_result)
        # DB purge runs outside the lock to avoid blocking other threads.
        self._purge_store(_expired)
        return _result

    def get_session(self, session_id: str) -> SessionState | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self, limit: int = 20, offset: int = 0) -> list["SessionState"]:
        """Return in-memory sessions ordered by most-recently-updated."""
        with self._lock:
            _expired = self._purge_expired()
            sorted_states = sorted(
                self._sessions.values(),
                key=lambda s: s.updated_at,
                reverse=True,
            )
            result = sorted_states[offset : offset + limit]
        # DB purge runs outside the lock to avoid blocking other threads.
        self._purge_store(_expired)
        return result

    def count_sessions(self) -> int:
        with self._lock:
            return len(self._sessions)

    # -- short-term memory ---------------------------------------------------

    def add_turn(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        tools_called: list[str] | None = None,
        tool_results: dict[str, Any] | None = None,
        tool_params: dict[str, dict] | None = None,
    ) -> SessionState:
        """Append a turn and return the updated session state.

        If tool results are large, they are automatically trimmed before storage.
        """
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                state = SessionState(session_id=session_id)
                self._sessions[session_id] = state

            # Trim large tool payloads
            safe_results = _compact_tool_results(tool_results) if tool_results else {}

            turn = Turn(
                role=role,
                content=content,
                tools_called=list(tools_called or []),
                tool_results=safe_results,
                tool_params=dict(tool_params or {}),
            )
            state.turns.append(turn)
            state.turns_since_summary += 1
            state.updated_at = time.time()
            if self._store is not None:
                self._store.append_turn(session_id, turn)
                self._store.save_session_meta(state)
            return state

    def get_recent_turns(self, session_id: str) -> list[Turn]:
        """Return the short-term window (last N turns)."""
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return []
            return list(state.turns[-self._short_term_max:])

    def needs_summarization(self, session_id: str) -> bool:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return False
            return state.turns_since_summary >= self._summarize_threshold

    def begin_summarization(self, session_id: str) -> bool:
        """Atomically mark summarization as in-progress.

        Returns True when the caller should proceed with summarization,
        False when another thread is already running it for this session.
        """
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None or state.summarization_in_progress:
                return False
            state.summarization_in_progress = True
            return True

    def end_summarization(self, session_id: str) -> None:
        """Clear the in-progress guard set by begin_summarization."""
        with self._lock:
            state = self._sessions.get(session_id)
            if state is not None:
                state.summarization_in_progress = False

    def apply_summary(self, session_id: str, summary: str) -> None:
        """Replace older turns with the new running summary.

        Keeps only the latest `short_term_max` turns; older ones are discarded
        since their content is captured in the summary.
        """
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return
            # Keep only the most recent turns
            state.turns = state.turns[-self._short_term_max:]
            state.summary = summary
            state.turns_since_summary = 0
            state.updated_at = time.time()
            if self._store is not None:
                self._store.delete_older_turns(state.session_id, self._short_term_max)
                self._store.save_session_meta(state)

    def get_summary(self, session_id: str) -> str:
        with self._lock:
            state = self._sessions.get(session_id)
            return state.summary if state else ""

    # -- long-term memory (fact store) ---------------------------------------

    def save_memory(self, session_id: str, item: MemoryItem) -> None:
        """Store a fact/entity/decision in long-term memory."""
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return
            # Deduplicate by content
            for existing in state.memory:
                if existing.content == item.content and existing.type == item.type:
                    return
            state.memory.append(item)
            # Evict oldest when over limit
            if len(state.memory) > self._long_term_max:
                state.memory = state.memory[-self._long_term_max:]
            state.updated_at = time.time()
            if self._store is not None:
                self._store.upsert_memory_item(session_id, item)

    def retrieve_memory(
        self, session_id: str, query: str, *, limit: int = 3
    ) -> list[MemoryItem]:
        """Retrieve relevant memory items using keyword + n-gram matching.

        Combines unigram overlap scoring with bigram overlap for better recall
        on paraphrased queries (e.g. "that order" matches "orderId: 12345").
        Returns at most ``limit`` items, most relevant first.
        """
        with self._lock:
            state = self._sessions.get(session_id)
            if state is None:
                return []
            query_lower = query.lower()
            query_tokens = set(query_lower.split())
            query_bigrams = _ngrams(query_lower, 2)
            scored: list[tuple[float, MemoryItem]] = []
            for item in state.memory:
                content_lower = item.content.lower()
                # Unigram score: fraction of query tokens found in content
                uni_matches = sum(1 for t in query_tokens if t in content_lower)
                uni_score = uni_matches / len(query_tokens) if query_tokens else 0.0
                # Bigram overlap bonus (boosts partial-phrase matches)
                bi_score = 0.0
                if query_bigrams:
                    content_bigrams = _ngrams(content_lower, 2)
                    bi_overlap = len(query_bigrams & content_bigrams)
                    bi_score = bi_overlap / len(query_bigrams) * 0.3  # 30% weight
                total_score = uni_score + bi_score
                if total_score > 0:
                    scored.append((total_score, item))
            scored.sort(key=lambda x: (-x[0], -x[1].created_at))
            return [item for _, item in scored[:limit]]

    # -- auto-extraction -----------------------------------------------------

    def extract_and_store_entities(self, session_id: str, text: str) -> list[MemoryItem]:
        """Scan text for known entity patterns and persist as long-term memory."""
        extracted: list[MemoryItem] = []
        for entity_name, pattern in _ENTITY_PATTERNS.items():
            for match in pattern.finditer(text):
                value = match.group(1) if match.lastindex else match.group(0)
                item = MemoryItem(
                    id=str(uuid.uuid4()),
                    type=MemoryType.ENTITY,
                    content=f"{entity_name}: {value}",
                )
                self.save_memory(session_id, item)
                extracted.append(item)
        return extracted

    # -- housekeeping --------------------------------------------------------

    def _purge_expired(self) -> list[str]:
        """Evict expired sessions from memory. Must be called under lock.

        Returns the list of evicted session IDs so the caller can run slow
        DB cleanup *outside* the lock.
        """
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if (now - s.updated_at) > self._ttl_seconds
        ]
        for sid in expired:
            self._sessions.pop(sid, None)
        return expired

    def _purge_store(self, expired: list[str]) -> None:
        """Delete expired sessions from the persistent store. Call outside any lock."""
        if expired and self._store is not None:
            self._store.purge_expired_sessions(self._ttl_seconds)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _ngrams(text: str, n: int) -> set[str]:
    """Return a set of character n-grams from *text* (lowercased)."""
    return {text[i : i + n] for i in range(len(text) - n + 1)} if len(text) >= n else set()


def _compact_tool_results(results: dict[str, Any]) -> dict[str, Any]:
    """Trim tool-result payloads that exceed the storage budget."""
    compacted: dict[str, Any] = {}
    for key, value in results.items():
        text = str(value)
        if len(text) > TOOL_RESULT_SUMMARY_LIMIT:
            compacted[key] = text[:TOOL_RESULT_SUMMARY_LIMIT] + "...[trimmed]"
        else:
            compacted[key] = value
    return compacted
