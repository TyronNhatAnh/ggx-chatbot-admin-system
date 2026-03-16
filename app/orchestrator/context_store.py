import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationTurn:
    user_message: str
    assistant_reply: str
    tools_called: list[str]
    created_at: float = field(default_factory=time.time)


@dataclass
class CachedOrderRecord:
    order: dict[str, Any]
    cached_at: float = field(default_factory=time.time)


@dataclass
class ConversationState:
    conversation_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    order_cache: dict[str, CachedOrderRecord] = field(default_factory=dict)
    last_focus_order_id: str | None = None
    updated_at: float = field(default_factory=time.time)


class ConversationStore(ABC):
    @abstractmethod
    def get_or_create(self, conversation_id: str | None) -> ConversationState:
        """Return an existing conversation state or create a new one."""

    @abstractmethod
    def append_turn(
        self,
        conversation_id: str,
        *,
        user_message: str,
        assistant_reply: str,
        tools_called: list[str],
    ) -> ConversationState:
        """Append one turn to the conversation and return updated state."""


class InMemoryConversationStore(ConversationStore):
    """Best-effort in-memory context store for single-process deployments."""

    def __init__(self, *, ttl_seconds: int = 1800, max_turns: int = 12) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_turns = max_turns
        self._items: dict[str, ConversationState] = {}
        self._lock = threading.Lock()

    def get_or_create(self, conversation_id: str | None) -> ConversationState:
        with self._lock:
            self._purge_expired_locked()

            normalized_id = (conversation_id or "").strip()
            if normalized_id and normalized_id in self._items:
                state = self._items[normalized_id]
                state.updated_at = time.time()
                return state

            new_id = normalized_id or str(uuid.uuid4())
            state = ConversationState(conversation_id=new_id)
            self._items[new_id] = state
            return state

    def append_turn(
        self,
        conversation_id: str,
        *,
        user_message: str,
        assistant_reply: str,
        tools_called: list[str],
    ) -> ConversationState:
        with self._lock:
            self._purge_expired_locked()

            state = self._items.get(conversation_id)
            if state is None:
                state = ConversationState(conversation_id=conversation_id)
                self._items[conversation_id] = state

            state.turns.append(
                ConversationTurn(
                    user_message=user_message,
                    assistant_reply=assistant_reply,
                    tools_called=list(tools_called),
                )
            )
            if len(state.turns) > self._max_turns:
                state.turns = state.turns[-self._max_turns :]

            state.updated_at = time.time()
            return state

    def _purge_expired_locked(self) -> None:
        now = time.time()
        expired = [
            cid
            for cid, state in self._items.items()
            if (now - state.updated_at) > self._ttl_seconds
        ]
        for cid in expired:
            self._items.pop(cid, None)