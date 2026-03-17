"""Persistent knowledge store backed by SQLite + JSON index files.

Stores extracted enums, service flows, struct definitions, and code chunks.
Provides fast lookup methods used by the chatbot knowledge tools at query time.

Design decisions:
  - SQLite (not a graph DB) keeps infrastructure simple — no Docker dependency.
  - JSON sidecar files provide human-readable snapshots for debugging.
  - FTS5 virtual table enables full-text search over code content.
  - All writes happen during indexing; reads happen at query time.
"""

import json
import logging
import sqlite3
from dataclasses import asdict
from pathlib import Path

from indexer.models import (
    CodeChunk,
    Edge,
    EnumGroup,
    EnumValue,
    ServiceFlow,
    StructDefinition,
)

logger = logging.getLogger(__name__)

_DEFAULT_DB_DIR = Path(__file__).parents[1] / "data" / "knowledge"
_DB_FILENAME = "knowledge.db"
_JSON_DIR = "json"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS enums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type_name TEXT NOT NULL,
    service TEXT NOT NULL DEFAULT '',
    file TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS enum_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    enum_id INTEGER NOT NULL REFERENCES enums(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    persona TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS struct_definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    service TEXT NOT NULL DEFAULT '',
    file TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT '',
    embedded_types TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS struct_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    struct_id INTEGER NOT NULL REFERENCES struct_definitions(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    json_tag TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT '',
    is_pointer INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS service_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    handler_name TEXT NOT NULL,
    handler_file TEXT NOT NULL DEFAULT '',
    endpoint TEXT NOT NULL DEFAULT '',
    service TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    service_calls_json TEXT NOT NULL DEFAULT '[]',
    repository_calls_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS code_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qualified_name TEXT NOT NULL,
    content TEXT NOT NULL,
    chunk_type TEXT NOT NULL,
    service TEXT NOT NULL DEFAULT '',
    file TEXT NOT NULL DEFAULT '',
    start_line INTEGER NOT NULL DEFAULT 0,
    end_line INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE VIRTUAL TABLE IF NOT EXISTS code_chunks_fts USING fts5(
    qualified_name, content, chunk_type, service,
    content='code_chunks',
    content_rowid='id'
);

CREATE INDEX IF NOT EXISTS idx_enums_name ON enums(name);
CREATE INDEX IF NOT EXISTS idx_enums_service ON enums(service);
CREATE INDEX IF NOT EXISTS idx_enum_values_value ON enum_values(value);
CREATE INDEX IF NOT EXISTS idx_struct_name ON struct_definitions(name);
CREATE INDEX IF NOT EXISTS idx_flows_handler ON service_flows(handler_name);
CREATE INDEX IF NOT EXISTS idx_chunks_type ON code_chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_chunks_name ON code_chunks(qualified_name);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_type TEXT NOT NULL,
    from_name TEXT NOT NULL,
    from_service TEXT NOT NULL DEFAULT '',
    edge_type TEXT NOT NULL,
    to_type TEXT NOT NULL,
    to_name TEXT NOT NULL,
    to_service TEXT NOT NULL DEFAULT '',
    file TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_name, edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_name, edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_edges_service ON edges(from_service);
"""

_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS code_chunks_ai AFTER INSERT ON code_chunks BEGIN
    INSERT INTO code_chunks_fts(rowid, qualified_name, content, chunk_type, service)
    VALUES (new.id, new.qualified_name, new.content, new.chunk_type, new.service);
END;

CREATE TRIGGER IF NOT EXISTS code_chunks_ad AFTER DELETE ON code_chunks BEGIN
    INSERT INTO code_chunks_fts(code_chunks_fts, rowid, qualified_name, content, chunk_type, service)
    VALUES ('delete', old.id, old.qualified_name, old.content, old.chunk_type, old.service);
END;
"""


class KnowledgeStore:
    """SQLite-backed knowledge store for indexed codebase entities."""

    def __init__(self, db_dir: Path | None = None):
        self._db_dir = db_dir or _DEFAULT_DB_DIR
        self._db_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._db_dir / _DB_FILENAME
        self._json_dir = self._db_dir / _JSON_DIR
        self._json_dir.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(_SCHEMA_SQL)
            self._conn.executescript(_FTS_TRIGGERS)
            self._migrate(self._conn)
        return self._conn

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Apply lightweight schema migrations for existing databases."""
        # Add persona column to enum_values if missing (added for disambiguation)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(enum_values)").fetchall()}
        if "persona" not in cols:
            conn.execute("ALTER TABLE enum_values ADD COLUMN persona TEXT NOT NULL DEFAULT ''")
            conn.commit()
            logger.info("[KnowledgeStore] Migrated: added persona column to enum_values")

        # Ensure edges table exists (Phase 1 graph evolution)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "edges" not in tables:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_type TEXT NOT NULL,
                    from_name TEXT NOT NULL,
                    from_service TEXT NOT NULL DEFAULT '',
                    edge_type TEXT NOT NULL,
                    to_type TEXT NOT NULL,
                    to_name TEXT NOT NULL,
                    to_service TEXT NOT NULL DEFAULT '',
                    file TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_name, edge_type);
                CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_name, edge_type);
                CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
                CREATE INDEX IF NOT EXISTS idx_edges_service ON edges(from_service);
            """)
            conn.commit()
            logger.info("[KnowledgeStore] Migrated: created edges table")

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Write methods (called during indexing)
    # ------------------------------------------------------------------

    def clear_service(self, service: str) -> None:
        """Remove all data for a specific service before re-indexing."""
        conn = self._get_conn()
        # Enum values via cascade
        conn.execute(
            "DELETE FROM enums WHERE service = ?", (service,)
        )
        # Struct fields via cascade
        conn.execute(
            "DELETE FROM struct_definitions WHERE service = ?", (service,)
        )
        conn.execute(
            "DELETE FROM service_flows WHERE service = ?", (service,)
        )
        conn.execute(
            "DELETE FROM code_chunks WHERE service = ?", (service,)
        )
        conn.execute(
            "DELETE FROM edges WHERE from_service = ? OR to_service = ?",
            (service, service),
        )
        conn.commit()
        logger.info("[KnowledgeStore] Cleared data for service=%s", service)

    def store_enums(self, groups: list[EnumGroup]) -> int:
        conn = self._get_conn()
        count = 0
        for g in groups:
            cursor = conn.execute(
                "INSERT INTO enums (name, type_name, service, file, comment) VALUES (?, ?, ?, ?, ?)",
                (g.name, g.type_name, g.service, g.file, g.comment),
            )
            enum_id = cursor.lastrowid
            for v in g.values:
                conn.execute(
                    "INSERT INTO enum_values (enum_id, name, value, comment, persona) VALUES (?, ?, ?, ?, ?)",
                    (enum_id, v.name, v.value, v.comment, getattr(v, 'persona', '')),
                )
            count += 1
        conn.commit()
        # Write JSON sidecar
        self._write_json("enums.json", [asdict(g) for g in groups])
        return count

    def store_structs(self, structs: list[StructDefinition]) -> int:
        conn = self._get_conn()
        count = 0
        for s in structs:
            cursor = conn.execute(
                "INSERT INTO struct_definitions (name, service, file, comment, embedded_types) "
                "VALUES (?, ?, ?, ?, ?)",
                (s.name, s.service, s.file, s.comment, json.dumps(s.embedded_types)),
            )
            struct_id = cursor.lastrowid
            for f in s.fields:
                conn.execute(
                    "INSERT INTO struct_fields (struct_id, name, type, json_tag, comment, is_pointer) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (struct_id, f.name, f.type, f.json_tag, f.comment, int(f.is_pointer)),
                )
            count += 1
        conn.commit()
        self._write_json("structs.json", [asdict(s) for s in structs])
        return count

    def store_flows(self, flows: list[ServiceFlow]) -> int:
        conn = self._get_conn()
        count = 0
        for f in flows:
            conn.execute(
                "INSERT INTO service_flows "
                "(handler_name, handler_file, endpoint, service, description, "
                "service_calls_json, repository_calls_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    f.handler_name, f.handler_file, f.endpoint, f.service,
                    f.description,
                    json.dumps([asdict(c) for c in f.service_calls]),
                    json.dumps([asdict(c) for c in f.repository_calls]),
                ),
            )
            count += 1
        conn.commit()
        self._write_json("flows.json", [asdict(f) for f in flows])
        return count

    def store_edges(self, edges: list[Edge]) -> int:
        """Store graph edges for traversal queries."""
        conn = self._get_conn()
        count = 0
        for e in edges:
            conn.execute(
                "INSERT INTO edges "
                "(from_type, from_name, from_service, edge_type, "
                "to_type, to_name, to_service, file, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    e.from_type, e.from_name, e.from_service, e.edge_type,
                    e.to_type, e.to_name, e.to_service, e.file,
                    json.dumps(e.metadata),
                ),
            )
            count += 1
        conn.commit()
        self._write_json("edges.json", [
            {"from": f"{e.from_type}:{e.from_name}", "edge": e.edge_type,
             "to": f"{e.to_type}:{e.to_name}", "file": e.file}
            for e in edges
        ])
        return count

    def store_code_chunks(self, chunks: list[CodeChunk]) -> int:
        conn = self._get_conn()
        count = 0
        for c in chunks:
            conn.execute(
                "INSERT INTO code_chunks "
                "(qualified_name, content, chunk_type, service, file, "
                "start_line, end_line, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    c.qualified_name, c.content, c.chunk_type,
                    c.service, c.file, c.start_line, c.end_line,
                    json.dumps(c.metadata),
                ),
            )
            count += 1
        conn.commit()
        return count

    # ------------------------------------------------------------------
    # Read methods (called at query time by knowledge tools)
    # ------------------------------------------------------------------

    def lookup_enum(self, name: str) -> dict:
        """Find an enum group by name (case-insensitive partial match).
        Returns all matching groups with their values.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, name, type_name, service, file, comment FROM enums "
            "WHERE LOWER(name) LIKE LOWER(?)",
            (f"%{name}%",),
        ).fetchall()

        results = []
        for row in rows:
            values = conn.execute(
                "SELECT name, value, comment, persona FROM enum_values WHERE enum_id = ? ORDER BY CAST(value AS INTEGER)",
                (row["id"],),
            ).fetchall()
            results.append({
                "name": row["name"],
                "type": row["type_name"],
                "service": row["service"],
                "file": row["file"],
                "comment": row["comment"],
                "values": [
                    {"name": v["name"], "value": v["value"], "description": v["comment"],
                     **(({"persona": v["persona"]}) if v["persona"] else {})}
                    for v in values
                ],
            })
        return {"matches": len(results), "enums": results}

    def explain_status_code(self, code: str) -> dict:
        """Look up what a specific status code value means across all enums.

        Filters out protobuf-generated and internal-only entries to keep
        results focused on business-relevant enums.
        Groups results by persona when available and flags ambiguity.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT ev.name, ev.value, ev.comment, ev.persona, e.name AS enum_name, "
            "e.type_name, e.service, e.file AS file "
            "FROM enum_values ev JOIN enums e ON ev.enum_id = e.id "
            "WHERE ev.value = ?",
            (str(code),),
        ).fetchall()

        # Filter out noise: protobuf, internal, and low-signal entries
        _SKIP_PREFIXES = ("pkg/grpc/", ".pb.go")
        _SKIP_NAMES = frozenset({"_"})  # blank identifiers

        ranked: list[dict] = []
        for r in rows:
            file_path = r["file"] or ""
            const_name = r["name"] or ""
            enum_name = r["enum_name"] or ""
            if any(file_path.endswith(sfx) or sfx in file_path for sfx in _SKIP_PREFIXES):
                continue
            if const_name in _SKIP_NAMES:
                continue

            # Priority: lower = more relevant. Status-related enums first.
            priority = 10
            name_lower = enum_name.lower()
            if "status" in name_lower:
                priority = 0
            elif "enumerate" in file_path or "domain" in file_path:
                priority = 2
            elif enum_name != "unnamed" and enum_name != "int":
                priority = 5

            entry: dict = {
                "_priority": priority,
                "enum": enum_name,
                "constant_name": const_name,
                "value": r["value"],
                "description": r["comment"],
                "type": r["type_name"],
                "service": r["service"],
                "file": file_path,
            }
            persona = (r["persona"] or "").strip()
            if persona:
                entry["persona"] = persona
            ranked.append(entry)

        ranked.sort(key=lambda x: x["_priority"])

        # Ensure persona diversity in top results: pick best entry per persona first,
        # then fill remaining slots with ungrouped entries.
        all_personas_present = {m.get("persona") for m in ranked if m.get("persona")}
        if len(all_personas_present) > 1:
            per_persona: dict[str, dict] = {}
            rest: list[dict] = []
            for m in ranked:
                p = m.get("persona", "")
                if p and p not in per_persona:
                    per_persona[p] = m
                else:
                    rest.append(m)
            # Persona entries first (sorted by priority), then rest
            selected = sorted(per_persona.values(), key=lambda x: x["_priority"])
            remaining_slots = 7 - len(selected)
            selected.extend(rest[:max(0, remaining_slots)])
            meanings = [{k: v for k, v in m.items() if k != "_priority"} for m in selected]
        else:
            meanings = [{k: v for k, v in m.items() if k != "_priority"} for m in ranked[:5]]

        # Detect persona ambiguity: multiple distinct personas for the same code
        personas_found = {m["persona"] for m in meanings if m.get("persona")}
        ambiguous = len(personas_found) > 1

        result: dict = {
            "code": code,
            "matches": len(meanings),
            "meanings": meanings,
        }
        if ambiguous:
            result["persona_ambiguous"] = True
            result["personas_found"] = sorted(personas_found)
            result["hint"] = (
                "This status code has different meanings depending on the perspective "
                f"({', '.join(sorted(personas_found))}). "
                "Ask the user which perspective they are asking about before answering."
            )
        return result

    def get_struct(self, name: str) -> dict:
        """Look up a struct definition by name (case-insensitive partial match)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, name, service, file, comment, embedded_types "
            "FROM struct_definitions WHERE LOWER(name) LIKE LOWER(?)",
            (f"%{name}%",),
        ).fetchall()

        results = []
        for row in rows:
            fields = conn.execute(
                "SELECT name, type, json_tag, comment, is_pointer "
                "FROM struct_fields WHERE struct_id = ? ORDER BY id",
                (row["id"],),
            ).fetchall()
            results.append({
                "name": row["name"],
                "service": row["service"],
                "file": row["file"],
                "comment": row["comment"],
                "embedded_types": json.loads(row["embedded_types"]),
                "fields": [
                    {
                        "name": f["name"],
                        "type": f["type"],
                        "json_tag": f["json_tag"],
                        "comment": f["comment"],
                        "nullable": bool(f["is_pointer"]),
                    }
                    for f in fields
                ],
            })
        return {"matches": len(results), "structs": results}

    def get_flow(self, handler_name: str) -> dict:
        """Look up the service flow for a handler function."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT handler_name, handler_file, endpoint, service, description, "
            "service_calls_json, repository_calls_json "
            "FROM service_flows WHERE LOWER(handler_name) LIKE LOWER(?)",
            (f"%{handler_name}%",),
        ).fetchall()

        return {
            "matches": len(rows),
            "flows": [
                {
                    "handler": r["handler_name"],
                    "file": r["handler_file"],
                    "endpoint": r["endpoint"],
                    "service": r["service"],
                    "description": r["description"],
                    "service_calls": json.loads(r["service_calls_json"]),
                    "repository_calls": json.loads(r["repository_calls_json"]),
                }
                for r in rows
            ],
        }

    def traverse(self, start_name: str, edge_types: list[str] | None = None,
                  direction: str = "outgoing", max_depth: int = 3,
                  limit: int = 50) -> dict:
        """Multi-hop graph traversal from a starting node.

        Args:
            start_name: Name (partial match) of the starting node.
            edge_types: Filter to specific edge types (None = all).
            direction: 'outgoing', 'incoming', or 'both'.
            max_depth: Maximum traversal depth.
            limit: Max edges to return.

        Returns:
            Dict with nodes visited and edges traversed.
        """
        conn = self._get_conn()

        # Seed: find starting edges
        visited_names: set[str] = set()
        all_edges: list[dict] = []

        # Resolve start node name(s) — partial match
        name_pattern = f"%{start_name}%"

        for depth in range(max_depth):
            if depth == 0:
                current_names = [name_pattern]
                is_first = True
            else:
                if not visited_names:
                    break
                current_names = list(visited_names - {e["from"] for e in all_edges} - {e["to"] for e in all_edges})
                if not current_names:
                    # Use all frontier nodes
                    if direction in ("outgoing", "both"):
                        current_names = list({e["to"] for e in all_edges[-limit:]})
                    else:
                        current_names = list({e["from"] for e in all_edges[-limit:]})
                is_first = False

            for name in current_names:
                if len(all_edges) >= limit:
                    break

                operator = "LIKE" if is_first else "="
                match_val = name if is_first else name

                if direction in ("outgoing", "both"):
                    q = (f"SELECT from_type, from_name, from_service, edge_type, "
                         f"to_type, to_name, to_service, file "
                         f"FROM edges WHERE from_name {operator} ?")
                    params: list = [match_val]
                    if edge_types:
                        placeholders = ",".join("?" * len(edge_types))
                        q += f" AND edge_type IN ({placeholders})"
                        params.extend(edge_types)
                    q += f" LIMIT ?"
                    params.append(limit - len(all_edges))

                    for r in conn.execute(q, params).fetchall():
                        edge_dict = {
                            "from": r["from_name"],
                            "from_type": r["from_type"],
                            "from_service": r["from_service"],
                            "edge": r["edge_type"],
                            "to": r["to_name"],
                            "to_type": r["to_type"],
                            "to_service": r["to_service"],
                            "file": r["file"],
                        }
                        all_edges.append(edge_dict)
                        visited_names.add(r["to_name"])

                if direction in ("incoming", "both"):
                    q = (f"SELECT from_type, from_name, from_service, edge_type, "
                         f"to_type, to_name, to_service, file "
                         f"FROM edges WHERE to_name {operator} ?")
                    params = [match_val]
                    if edge_types:
                        placeholders = ",".join("?" * len(edge_types))
                        q += f" AND edge_type IN ({placeholders})"
                        params.extend(edge_types)
                    q += f" LIMIT ?"
                    params.append(limit - len(all_edges))

                    for r in conn.execute(q, params).fetchall():
                        edge_dict = {
                            "from": r["from_name"],
                            "from_type": r["from_type"],
                            "from_service": r["from_service"],
                            "edge": r["edge_type"],
                            "to": r["to_name"],
                            "to_type": r["to_type"],
                            "to_service": r["to_service"],
                            "file": r["file"],
                        }
                        all_edges.append(edge_dict)
                        visited_names.add(r["from_name"])

        # Deduplicate edges
        seen: set[str] = set()
        unique_edges: list[dict] = []
        for e in all_edges:
            key = f"{e['from']}|{e['edge']}|{e['to']}"
            if key not in seen:
                seen.add(key)
                unique_edges.append(e)

        return {
            "start": start_name,
            "direction": direction,
            "depth": max_depth,
            "edges_found": len(unique_edges),
            "edges": unique_edges[:limit],
        }

    def find_edges(self, name: str, edge_type: str | None = None,
                   direction: str = "both", limit: int = 20) -> dict:
        """Find direct edges for a node (1-hop only). Fast lookup."""
        conn = self._get_conn()
        results: list[dict] = []
        pattern = f"%{name}%"

        if direction in ("outgoing", "both"):
            q = ("SELECT from_type, from_name, from_service, edge_type, "
                 "to_type, to_name, to_service, file "
                 "FROM edges WHERE from_name LIKE ?")
            params: list = [pattern]
            if edge_type:
                q += " AND edge_type = ?"
                params.append(edge_type)
            q += " LIMIT ?"
            params.append(limit)
            for r in conn.execute(q, params).fetchall():
                results.append({
                    "from": r["from_name"], "from_type": r["from_type"],
                    "edge": r["edge_type"],
                    "to": r["to_name"], "to_type": r["to_type"],
                    "to_service": r["to_service"], "file": r["file"],
                })

        if direction in ("incoming", "both"):
            q = ("SELECT from_type, from_name, from_service, edge_type, "
                 "to_type, to_name, to_service, file "
                 "FROM edges WHERE to_name LIKE ?")
            params = [pattern]
            if edge_type:
                q += " AND edge_type = ?"
                params.append(edge_type)
            q += " LIMIT ?"
            params.append(limit)
            for r in conn.execute(q, params).fetchall():
                results.append({
                    "from": r["from_name"], "from_type": r["from_type"],
                    "edge": r["edge_type"],
                    "to": r["to_name"], "to_type": r["to_type"],
                    "to_service": r["to_service"], "file": r["file"],
                })

        return {"name": name, "matches": len(results), "edges": results}

    def search_code(self, query: str, limit: int = 10) -> dict:
        """Full-text search over indexed code chunks."""
        conn = self._get_conn()
        # Sanitize query for FTS5
        safe_query = " ".join(
            word for word in query.split() if word.isalnum()
        )
        if not safe_query:
            return {"matches": 0, "results": []}

        rows = conn.execute(
            "SELECT c.qualified_name, c.chunk_type, c.service, c.file, "
            "c.start_line, c.end_line, "
            "snippet(code_chunks_fts, 1, '>>>', '<<<', '...', 64) AS snippet "
            "FROM code_chunks_fts f "
            "JOIN code_chunks c ON f.rowid = c.id "
            "WHERE code_chunks_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (safe_query, limit),
        ).fetchall()

        return {
            "query": query,
            "matches": len(rows),
            "results": [
                {
                    "qualified_name": r["qualified_name"],
                    "type": r["chunk_type"],
                    "service": r["service"],
                    "file": r["file"],
                    "lines": f"{r['start_line']}-{r['end_line']}",
                    "snippet": r["snippet"],
                }
                for r in rows
            ],
        }

    def trace_full_stack(self, endpoint: str, limit: int = 30) -> dict:
        """Trace a full-stack path: React page -> API -> Go handler -> service -> repo.

        Given an API endpoint (partial match), walks the graph in both
        directions to reconstruct the complete request flow across services.

        Returns:
            Dict with the endpoint, upstream consumers (React components/pages),
            and downstream implementation chain (handler -> service -> repo).
        """
        conn = self._get_conn()
        pattern = f"%{endpoint}%"

        # --- Find matching api_endpoint nodes via handles edges ---
        be_rows = conn.execute(
            "SELECT from_name, to_name, to_service, file "
            "FROM edges WHERE edge_type = 'handles' AND from_name LIKE ? LIMIT ?",
            (pattern, limit),
        ).fetchall()

        if not be_rows:
            # Try matching by handler name instead
            be_rows = conn.execute(
                "SELECT from_name, to_name, to_service, file "
                "FROM edges WHERE edge_type = 'handles' AND to_name LIKE ? LIMIT ?",
                (pattern, limit),
            ).fetchall()

        matched_endpoints: list[str] = []
        handlers: list[dict] = []
        seen_handlers: set[str] = set()

        for r in be_rows:
            ep = r["from_name"]
            handler = r["to_name"]
            if ep not in matched_endpoints:
                matched_endpoints.append(ep)
            if handler in seen_handlers:
                continue
            seen_handlers.add(handler)

            # Downstream: handler -> service calls, handler -> repo calls
            svc_calls = conn.execute(
                "SELECT to_name, to_type FROM edges "
                "WHERE from_name = ? AND edge_type = 'calls' LIMIT ?",
                (handler, limit),
            ).fetchall()
            repo_calls = conn.execute(
                "SELECT to_name, to_type FROM edges "
                "WHERE from_name = ? AND edge_type = 'delegates_to' LIMIT ?",
                (handler, limit),
            ).fetchall()

            handlers.append({
                "handler": handler,
                "service": r["to_service"],
                "file": r["file"],
                "service_calls": [row["to_name"] for row in svc_calls],
                "repository_calls": [row["to_name"] for row in repo_calls],
            })

        # --- Upstream: find React components that call these endpoints ---
        consumers: list[dict] = []
        seen_consumers: set[str] = set()

        for ep in matched_endpoints:
            # Direct calls_api edges (React component -> api_endpoint)
            fe_rows = conn.execute(
                "SELECT from_name, from_type, from_service, file "
                "FROM edges WHERE to_name = ? AND edge_type IN ('calls_api', 'x_calls') "
                "LIMIT ?",
                (ep, limit),
            ).fetchall()
            for fr in fe_rows:
                if fr["from_name"] in seen_consumers:
                    continue
                seen_consumers.add(fr["from_name"])

                # Check if this component has a route
                route_row = conn.execute(
                    "SELECT from_name FROM edges "
                    "WHERE to_name = ? AND edge_type = 'routes_to' LIMIT 1",
                    (fr["from_name"],),
                ).fetchone()

                consumer: dict = {
                    "component": fr["from_name"],
                    "type": fr["from_type"],
                    "service": fr["from_service"],
                    "file": fr["file"],
                }
                if route_row:
                    consumer["route"] = route_row["from_name"]
                consumers.append(consumer)

        return {
            "endpoints": matched_endpoints,
            "matches": len(matched_endpoints),
            "consumers": consumers,
            "handlers": handlers,
        }

    def get_stats(self) -> dict:
        """Return summary statistics of indexed knowledge."""
        conn = self._get_conn()
        return {
            "enums": conn.execute("SELECT COUNT(*) FROM enums").fetchone()[0],
            "enum_values": conn.execute("SELECT COUNT(*) FROM enum_values").fetchone()[0],
            "structs": conn.execute("SELECT COUNT(*) FROM struct_definitions").fetchone()[0],
            "flows": conn.execute("SELECT COUNT(*) FROM service_flows").fetchone()[0],
            "code_chunks": conn.execute("SELECT COUNT(*) FROM code_chunks").fetchone()[0],
            "edges": conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0],
            "services": [
                r[0] for r in conn.execute(
                    "SELECT DISTINCT service FROM enums UNION "
                    "SELECT DISTINCT service FROM service_flows"
                ).fetchall()
            ],
            "edge_types": {
                r[0]: r[1] for r in conn.execute(
                    "SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type ORDER BY COUNT(*) DESC"
                ).fetchall()
            },
        }

    # ------------------------------------------------------------------
    # Endpoint / handler queries (replaces explorer/docs_tools deps)
    # ------------------------------------------------------------------

    def search_endpoints(self, keyword: str, limit: int = 30) -> list[dict]:
        """Search indexed endpoints (handles edges + service_flows) by keyword.

        Matches against endpoint path, handler name, and service name.
        Returns list of dicts with method, path, handler, service, file,
        and service_calls.
        """
        conn = self._get_conn()
        term = f"%{keyword.strip().lower()}%"

        # Search handles edges for endpoint → handler mappings
        rows = conn.execute(
            "SELECT e.from_name AS endpoint, e.to_name AS handler, "
            "e.to_service AS service, e.file "
            "FROM edges e "
            "WHERE e.edge_type = 'handles' "
            "AND (LOWER(e.from_name) LIKE ? OR LOWER(e.to_name) LIKE ?) "
            "LIMIT ?",
            (term, term, limit),
        ).fetchall()

        results: list[dict] = []
        for r in rows:
            endpoint = r["endpoint"]
            parts = endpoint.split(None, 1)
            method = parts[0] if len(parts) == 2 else ""
            path = parts[1] if len(parts) == 2 else endpoint

            handler_name = r["handler"].rsplit(".", 1)[-1] if "." in r["handler"] else r["handler"]

            # Get service calls from service_flows
            flow_row = conn.execute(
                "SELECT service_calls_json, repository_calls_json "
                "FROM service_flows WHERE handler_name = ? AND service = ? LIMIT 1",
                (handler_name, r["service"]),
            ).fetchone()

            service_calls: list[str] = []
            if flow_row:
                import json as _json
                try:
                    svc = _json.loads(flow_row["service_calls_json"])
                    service_calls = [
                        f"{c['receiver']}.{c['method']}()" for c in svc if isinstance(c, dict)
                    ]
                    repo = _json.loads(flow_row["repository_calls_json"])
                    service_calls += [
                        f"{c['receiver']}.{c['method']}()" for c in repo if isinstance(c, dict)
                    ]
                except (ValueError, KeyError):
                    pass

            results.append({
                "method": method,
                "path": path,
                "controller_method": handler_name,
                "service": r["service"],
                "file": r["file"],
                "service_calls": service_calls,
            })

        return results

    def get_handler_context(self, handler_name: str) -> dict | None:
        """Get handler source code from code_chunks (chunk_type='handler').

        Returns dict with handler name, source code, endpoint, service calls,
        or None if not found.
        """
        conn = self._get_conn()
        safe = handler_name.strip()

        # Match by method name suffix (qualified_name = service.ReceiverType.Method)
        row = conn.execute(
            "SELECT qualified_name, content, service, file, "
            "start_line, end_line, metadata_json "
            "FROM code_chunks "
            "WHERE chunk_type = 'handler' "
            "AND (qualified_name LIKE ? OR qualified_name = ?) "
            "ORDER BY qualified_name LIMIT 1",
            (f"%.{safe}", safe),
        ).fetchone()

        if not row:
            return None

        metadata = {}
        try:
            metadata = json.loads(row["metadata_json"])
        except (ValueError, KeyError):
            pass

        return {
            "handler": row["qualified_name"].rsplit(".", 1)[-1],
            "qualified_name": row["qualified_name"],
            "service": row["service"],
            "file": row["file"],
            "start_line": row["start_line"],
            "end_line": row["end_line"],
            "endpoint": metadata.get("endpoint", ""),
            "receiver_type": metadata.get("receiver_type", ""),
            "service_calls": metadata.get("service_calls", []),
            "source_code": row["content"],
        }

    def list_handlers(self) -> list[str]:
        """List all indexed handler names (from handler code chunks).

        Returns method names only. For generic names (Handle, Handler) that appear
        across multiple receiver types, includes ReceiverType.MethodName.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT qualified_name FROM code_chunks WHERE chunk_type = 'handler' "
            "ORDER BY qualified_name"
        ).fetchall()
        # qualified_name = service.ReceiverType.MethodName
        names: list[str] = []
        method_count: dict[str, int] = {}
        for r in rows:
            parts = r["qualified_name"].split(".")
            method = parts[-1] if parts else r["qualified_name"]
            method_count[method] = method_count.get(method, 0) + 1

        seen: dict[str, int] = {}
        for r in rows:
            parts = r["qualified_name"].split(".")
            method = parts[-1] if parts else r["qualified_name"]
            if method_count[method] > 1 and len(parts) >= 2:
                # Include receiver type for disambiguation
                display = f"{parts[-2]}.{method}" if len(parts) >= 2 else method
            else:
                display = method
            if display not in seen:
                seen[display] = 0
                names.append(display)

        return names

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_json(self, filename: str, data: list[dict]) -> None:
        """Write a JSON sidecar file for human-readable inspection."""
        path = self._json_dir / filename
        try:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("[KnowledgeStore] Failed to write %s: %s", path, e)


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_store: KnowledgeStore | None = None


def get_knowledge_store() -> KnowledgeStore:
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store
