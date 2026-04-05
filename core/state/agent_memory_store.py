import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AgentMemoryStore:
    """Persistent memory for agent interactions and relationship context."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        return con

    @contextmanager
    def _connection(self):
        con = self._connect()
        try:
            yield con
        finally:
            con.close()

    def _ensure_schema(self) -> None:
        with self._connection() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_name TEXT PRIMARY KEY,
                    agent_class TEXT NOT NULL,
                    has_llm INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL,
                    task TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    endpoint TEXT,
                    user_name TEXT,
                    employer_name TEXT,
                    project_name TEXT,
                    counterpart_agent TEXT,
                    summary TEXT,
                    details_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_interactions_agent_created
                ON interactions(agent_name, created_at DESC);

                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    relation_key TEXT NOT NULL,
                    interaction_count INTEGER NOT NULL DEFAULT 0,
                    last_seen_at TEXT NOT NULL,
                    meta_json TEXT,
                    UNIQUE(agent_name, relation_type, relation_key)
                );

                CREATE INDEX IF NOT EXISTS idx_relationships_agent
                ON relationships(agent_name);
                """
            )
            con.commit()

    def register_agent(self, agent_name: str, agent_class: str, has_llm: bool) -> None:
        key = (agent_name or "").strip().lower()
        if not key:
            return
        now = datetime.now(timezone.utc).isoformat()
        klass = (agent_class or "prime").strip().lower()
        if klass not in {"prime", "core"}:
            klass = "prime"
        with self._connection() as con:
            con.execute(
                """
                INSERT INTO agents(agent_name, agent_class, has_llm, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(agent_name) DO UPDATE SET
                  agent_class=excluded.agent_class,
                  has_llm=excluded.has_llm,
                  updated_at=excluded.updated_at
                """,
                (key, klass, 1 if has_llm else 0, now, now),
            )
            con.commit()

    def _touch_relationship(
        self,
        con: sqlite3.Connection,
        agent_name: str,
        relation_type: str,
        relation_key: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        if not relation_key:
            return
        now = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(meta or {}, ensure_ascii=True)
        con.execute(
            """
            INSERT INTO relationships(agent_name, relation_type, relation_key, interaction_count, last_seen_at, meta_json)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(agent_name, relation_type, relation_key)
            DO UPDATE SET
              interaction_count = interaction_count + 1,
              last_seen_at = excluded.last_seen_at,
              meta_json = excluded.meta_json
            """,
            (agent_name, relation_type, relation_key, now, meta_json),
        )

    def record_interaction(
        self,
        *,
        agent_name: str,
        task: str,
        success: bool,
        endpoint: str = "",
        user_name: str = "",
        employer_name: str = "",
        project_name: str = "",
        counterpart_agent: str = "",
        summary: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        key = (agent_name or "").strip().lower()
        if not key:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._connection() as con:
            con.execute(
                """
                INSERT INTO interactions(
                    agent_name, task, success, endpoint, user_name, employer_name, project_name,
                    counterpart_agent, summary, details_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key,
                    (task or "").strip(),
                    1 if success else 0,
                    (endpoint or "").strip(),
                    (user_name or "").strip(),
                    (employer_name or "").strip(),
                    (project_name or "").strip(),
                    (counterpart_agent or "").strip().lower(),
                    (summary or "").strip(),
                    json.dumps(details or {}, ensure_ascii=True),
                    now,
                ),
            )

            self._touch_relationship(con, key, "user", (user_name or "").strip(), {"source": "interaction"})
            self._touch_relationship(con, key, "employer", (employer_name or "").strip(), {"source": "interaction"})
            self._touch_relationship(con, key, "project", (project_name or "").strip(), {"source": "interaction"})
            self._touch_relationship(
                con,
                key,
                "agent",
                (counterpart_agent or "").strip().lower(),
                {"source": "interaction"},
            )
            con.commit()

    def recall_interactions(self, agent_name: str, limit: int = 25) -> list[dict[str, Any]]:
        key = (agent_name or "").strip().lower()
        if not key:
            return []
        safe_limit = max(1, min(int(limit), 200))
        with self._connection() as con:
            rows = con.execute(
                """
                SELECT agent_name, task, success, endpoint, user_name, employer_name, project_name,
                       counterpart_agent, summary, details_json, created_at
                FROM interactions
                WHERE agent_name = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (key, safe_limit),
            ).fetchall()

        out: list[dict[str, Any]] = []
        for row in rows:
            details_raw = row["details_json"] or "{}"
            try:
                details = json.loads(details_raw)
            except (json.JSONDecodeError, TypeError):
                details = {}
            out.append(
                {
                    "agent": row["agent_name"],
                    "task": row["task"],
                    "success": bool(row["success"]),
                    "endpoint": row["endpoint"],
                    "user": row["user_name"],
                    "employer": row["employer_name"],
                    "project": row["project_name"],
                    "counterpart_agent": row["counterpart_agent"],
                    "summary": row["summary"],
                    "details": details,
                    "created_at": row["created_at"],
                }
            )
        return out

    def list_relationships(self, agent_name: str) -> list[dict[str, Any]]:
        key = (agent_name or "").strip().lower()
        if not key:
            return []
        with self._connection() as con:
            rows = con.execute(
                """
                SELECT relation_type, relation_key, interaction_count, last_seen_at, meta_json
                FROM relationships
                WHERE agent_name = ?
                ORDER BY interaction_count DESC, last_seen_at DESC
                """,
                (key,),
            ).fetchall()

        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                meta = json.loads(row["meta_json"] or "{}")
            except (json.JSONDecodeError, TypeError):
                meta = {}
            out.append(
                {
                    "type": row["relation_type"],
                    "key": row["relation_key"],
                    "interaction_count": int(row["interaction_count"]),
                    "last_seen_at": row["last_seen_at"],
                    "meta": meta,
                }
            )
        return out
