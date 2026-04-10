"""Redis-backed store for chat session persistence.

Drop-in replacement for ChatStore — same public interface.
Enabled by setting ``REDIS_URL`` in .env (e.g. ``redis://localhost:6379/0``).

Sessions are stored as Redis hashes; turns and memory as JSON lists.
TTL is applied per-session (default SESSION_TTL_SECONDS = 1800).
Safe for multi-instance (multi-pod) deployments.
"""

import json
import logging
import time
from typing import Any

from app.orchestrator.memory_service import (
    MemoryItem,
    MemoryType,
    SESSION_TTL_SECONDS,
    SessionState,
    Turn,
)

logger = logging.getLogger(__name__)

# Redis key layout:
#   session:<id>:meta        — HASH  {summary, turns_since_summary, feature_key, updated_at}
#   session:<id>:turns       — LIST  [json, ...]  (oldest → newest)
#   session:<id>:memory      — LIST  [json, ...]


class RedisStore:
    """Multi-instance-safe session store backed by Redis."""

    def __init__(self, url: str, ttl_seconds: int = SESSION_TTL_SECONDS) -> None:
        import redis  # imported lazily so missing dep only fails when Redis is configured

        self._ttl = ttl_seconds
        self._client = redis.from_url(url, decode_responses=True)
        logger.info("[RedisStore] connected to %s", url)

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _meta_key(sid: str) -> str:
        return f"session:{sid}:meta"

    @staticmethod
    def _turns_key(sid: str) -> str:
        return f"session:{sid}:turns"

    @staticmethod
    def _memory_key(sid: str) -> str:
        return f"session:{sid}:memory"

    def _refresh_ttl(self, sid: str) -> None:
        for key in (self._meta_key(sid), self._turns_key(sid), self._memory_key(sid)):
            self._client.expire(key, self._ttl)

    # ------------------------------------------------------------------
    # Session read / write — same interface as ChatStore
    # ------------------------------------------------------------------

    def load_session(self, session_id: str) -> SessionState | None:
        meta = self._client.hgetall(self._meta_key(session_id))
        if not meta:
            return None

        state = SessionState(session_id=session_id)
        state.summary = meta.get("summary", "")
        state.turns_since_summary = int(meta.get("turns_since_summary", 0))
        state.feature_key = meta.get("feature_key") or None
        state.updated_at = float(meta.get("updated_at", time.time()))
        state.turns = self._load_turns(session_id)
        state.memory = self._load_memory(session_id)
        return state

    def save_session_meta(self, state: SessionState) -> None:
        self._client.hset(
            self._meta_key(state.session_id),
            mapping={
                "summary": state.summary or "",
                "turns_since_summary": state.turns_since_summary,
                "feature_key": state.feature_key or "",
                "updated_at": state.updated_at,
            },
        )
        self._refresh_ttl(state.session_id)

    def append_turn(self, session_id: str, turn: Turn) -> None:
        payload = json.dumps({
            "role": turn.role,
            "content": turn.content,
            "tools_called": turn.tools_called,
            "tool_results": turn.tool_results,
            "tool_params": turn.tool_params,
            "created_at": turn.created_at,
        })
        self._client.rpush(self._turns_key(session_id), payload)
        self._refresh_ttl(session_id)

    def upsert_memory_item(self, session_id: str, item: MemoryItem) -> None:
        # Check for duplicates by id before appending
        raw_list = self._client.lrange(self._memory_key(session_id), 0, -1)
        for raw in raw_list:
            existing = json.loads(raw)
            if existing.get("id") == item.id:
                return  # already stored — idempotent
        payload = json.dumps({
            "id": item.id,
            "type": item.type.value,
            "content": item.content,
            "created_at": item.created_at,
        })
        self._client.rpush(self._memory_key(session_id), payload)
        self._refresh_ttl(session_id)

    def delete_older_turns(self, session_id: str, keep_last_n: int) -> None:
        total = self._client.llen(self._turns_key(session_id))
        to_remove = total - keep_last_n
        if to_remove > 0:
            self._client.ltrim(self._turns_key(session_id), to_remove, -1)
        self._refresh_ttl(session_id)

    def purge_expired_sessions(self, ttl_seconds: int) -> None:
        # Redis TTL handles expiry automatically — this is a no-op.
        pass

    def list_sessions(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """Scan all session meta keys and return sorted by updated_at."""
        keys = list(self._client.scan_iter("session:*:meta"))
        sessions = []
        for key in keys:
            meta = self._client.hgetall(key)
            if not meta:
                continue
            sid = key.split(":")[1]
            turn_count = self._client.llen(self._turns_key(sid))
            sessions.append({
                "conversation_id": sid,
                "summary": meta.get("summary", ""),
                "updated_at": float(meta.get("updated_at", 0)),
                "turn_count": turn_count,
            })
        sessions.sort(key=lambda s: s["updated_at"], reverse=True)
        return sessions[offset: offset + limit]

    def count_sessions(self) -> int:
        return sum(1 for _ in self._client.scan_iter("session:*:meta"))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_turns(self, session_id: str) -> list[Turn]:
        raw_list = self._client.lrange(self._turns_key(session_id), 0, -1)
        turns = []
        for raw in raw_list:
            d = json.loads(raw)
            t = Turn(
                role=d["role"],
                content=d["content"],
                tools_called=d.get("tools_called", []),
                tool_results=d.get("tool_results", {}),
                tool_params=d.get("tool_params", {}),
                created_at=d.get("created_at", time.time()),
            )
            turns.append(t)
        return turns

    def _load_memory(self, session_id: str) -> list[MemoryItem]:
        raw_list = self._client.lrange(self._memory_key(session_id), 0, -1)
        items = []
        for raw in raw_list:
            d = json.loads(raw)
            items.append(MemoryItem(
                id=d["id"],
                type=MemoryType(d["type"]),
                content=d["content"],
                created_at=d.get("created_at", time.time()),
            ))
        return items
