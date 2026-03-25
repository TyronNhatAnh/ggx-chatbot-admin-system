"""SQLite-backed store for chat session persistence.

Enabled by setting ``CHAT_HISTORY_DB`` in the environment / .env file to a
file path (e.g. ``data/chat_history.db``).  When the value is empty (default)
the store is never instantiated and the application behaves exactly as before.
"""

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from app.orchestrator.memory_service import MemoryItem, MemoryType, SessionState, Turn

logger = logging.getLogger(__name__)

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
    session_id            TEXT PRIMARY KEY,
    summary               TEXT    NOT NULL DEFAULT '',
    turns_since_summary   INTEGER NOT NULL DEFAULT 0,
    feature_key           TEXT    DEFAULT NULL,
    updated_at            REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS turns (
    id           TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    role         TEXT NOT NULL,
    content      TEXT NOT NULL,
    tools_called TEXT NOT NULL DEFAULT '[]',
    tool_results TEXT NOT NULL DEFAULT '{}',
    created_at   REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS memory_items (
    id         TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    type       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_turns_session   ON turns(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_memory_session  ON memory_items(session_id, created_at);
"""


class ChatStore:
    """Thread-safe SQLite repository for persistent chat history.

    Each thread gets its own connection to satisfy SQLite's thread-safety
    requirements without serialising all access through a single lock.
    """

    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._local = threading.local()
        self._init_schema()
        logger.info("[ChatStore] Persistence enabled — %s", db_path)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self) -> None:
        self._conn().executescript(_DDL)
        self._migrate_feature_key()

    def _migrate_feature_key(self) -> None:
        """Add feature_key column to sessions if missing (upgrading from older schema)."""
        conn = self._conn()
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "feature_key" not in columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN feature_key TEXT DEFAULT NULL")
            conn.commit()
            logger.info("[ChatStore] Migrated sessions table — added feature_key column")

    # ------------------------------------------------------------------
    # Session read / write
    # ------------------------------------------------------------------

    def load_session(self, session_id: str) -> SessionState | None:
        """Hydrate a full SessionState from the database, or return None."""
        conn = self._conn()
        row = conn.execute(
            "SELECT summary, turns_since_summary, feature_key, updated_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None

        turns = self._load_turns(conn, session_id)
        memory = self._load_memory_items(conn, session_id)

        state = SessionState(session_id=session_id)
        state.summary = row["summary"]
        state.turns_since_summary = row["turns_since_summary"]
        state.feature_key = row["feature_key"]
        state.updated_at = row["updated_at"]
        state.turns = turns
        state.memory = memory
        return state

    def save_session_meta(self, state: SessionState) -> None:
        """Upsert the session row (summary + counters + feature_key + timestamp)."""
        conn = self._conn()
        conn.execute(
            """
            INSERT INTO sessions(session_id, summary, turns_since_summary, feature_key, updated_at)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                summary             = excluded.summary,
                turns_since_summary = excluded.turns_since_summary,
                feature_key         = excluded.feature_key,
                updated_at          = excluded.updated_at
            """,
            (state.session_id, state.summary, state.turns_since_summary, state.feature_key, state.updated_at),
        )
        conn.commit()

    def append_turn(self, session_id: str, turn: Turn) -> None:
        """Persist a single turn; safe to call multiple times (INSERT OR IGNORE)."""
        conn = self._conn()
        conn.execute(
            """
            INSERT OR IGNORE INTO turns(id, session_id, role, content, tools_called, tool_results, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                session_id,
                turn.role,
                turn.content,
                json.dumps(turn.tools_called),
                json.dumps(turn.tool_results),
                turn.created_at,
            ),
        )
        conn.commit()

    def upsert_memory_item(self, session_id: str, item: MemoryItem) -> None:
        """Persist a long-term memory item (INSERT OR IGNORE for idempotency)."""
        conn = self._conn()
        conn.execute(
            """
            INSERT OR IGNORE INTO memory_items(id, session_id, type, content, created_at)
            VALUES(?, ?, ?, ?, ?)
            """,
            (item.id, session_id, item.type.value, item.content, item.created_at),
        )
        conn.commit()

    def delete_older_turns(self, session_id: str, keep_last_n: int) -> None:
        """Remove turns beyond the most recent `keep_last_n` (called after summarization)."""
        conn = self._conn()
        conn.execute(
            """
            DELETE FROM turns
            WHERE session_id = ?
              AND id NOT IN (
                  SELECT id FROM turns
                  WHERE session_id = ?
                  ORDER BY created_at DESC
                  LIMIT ?
              )
            """,
            (session_id, session_id, keep_last_n),
        )
        conn.commit()

    def purge_expired_sessions(self, ttl_seconds: int) -> None:
        """Delete sessions (and their turns/memory via CASCADE) that exceeded TTL."""
        cutoff = time.time() - ttl_seconds
        conn = self._conn()
        conn.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))
        conn.commit()

    def list_sessions(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """List sessions ordered by most-recently-updated, with turn counts."""
        conn = self._conn()
        rows = conn.execute(
            """
            SELECT s.session_id, s.summary, s.updated_at,
                   COUNT(t.id) AS turn_count
            FROM sessions s
            LEFT JOIN turns t ON t.session_id = s.session_id
            GROUP BY s.session_id
            ORDER BY s.updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [
            {
                "conversation_id": row["session_id"],
                "summary": row["summary"],
                "updated_at": row["updated_at"],
                "turn_count": row["turn_count"],
            }
            for row in rows
        ]

    def count_sessions(self) -> int:
        """Return total number of sessions."""
        row = self._conn().execute("SELECT COUNT(*) FROM sessions").fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_turns(self, conn: sqlite3.Connection, session_id: str) -> list[Turn]:
        rows = conn.execute(
            """
            SELECT role, content, tools_called, tool_results, created_at
            FROM turns
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        ).fetchall()
        turns: list[Turn] = []
        for row in rows:
            t = Turn(role=row["role"], content=row["content"])
            t.tools_called = json.loads(row["tools_called"])
            t.tool_results = json.loads(row["tool_results"])
            t.created_at = row["created_at"]
            turns.append(t)
        return turns

    def _load_memory_items(self, conn: sqlite3.Connection, session_id: str) -> list[MemoryItem]:
        rows = conn.execute(
            """
            SELECT id, type, content, created_at
            FROM memory_items
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        ).fetchall()
        items: list[MemoryItem] = []
        for row in rows:
            items.append(
                MemoryItem(
                    id=row["id"],
                    type=MemoryType(row["type"]),
                    content=row["content"],
                    created_at=row["created_at"],
                )
            )
        return items
