"""
SQLite implementation of ScriptStore, TrajectoryStore, SessionStore.
Single DB file (e.g. zerotoken.db); tables: scripts, trajectories, session_headers, session_steps.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .storage import ScriptStore, TrajectoryStore, SessionStore


def _json_serializer(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _json_deserializer(s: Optional[str]) -> Any:
    if s is None:
        return None
    return json.loads(s)


class SQLiteStorage(ScriptStore, TrajectoryStore, SessionStore):
    """Single SQLite-backed storage for scripts, trajectories, and sessions."""

    def __init__(self, db_path: str = "zerotoken.db"):
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_tables()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_tables(self) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scripts (
                task_id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                steps TEXT NOT NULL,
                params_schema TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trajectories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                goal TEXT NOT NULL,
                operations TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS session_headers (
                session_id TEXT PRIMARY KEY,
                task_id TEXT,
                session_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS session_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                action TEXT NOT NULL,
                selector TEXT,
                url TEXT,
                timestamp TEXT NOT NULL,
                payload TEXT,
                FOREIGN KEY (session_id) REFERENCES session_headers(session_id)
            )
        """)
        self.conn.commit()

    # --- ScriptStore ---
    def script_save(
        self,
        task_id: str,
        *,
        goal: str,
        steps: List[Dict[str, Any]],
        params_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.utcnow().isoformat() + "Z"
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO scripts (task_id, goal, steps, params_schema, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                goal = excluded.goal,
                steps = excluded.steps,
                params_schema = excluded.params_schema,
                updated_at = excluded.updated_at
            """,
            (task_id, goal, _json_serializer(steps), _json_serializer(params_schema or {}), now, now),
        )
        self.conn.commit()

    def script_load(self, task_id: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT task_id, goal, steps, params_schema, created_at, updated_at FROM scripts WHERE task_id = ?", (task_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "task_id": row["task_id"],
            "goal": row["goal"],
            "steps": _json_deserializer(row["steps"]),
            "params_schema": _json_deserializer(row["params_schema"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def script_list(self, limit: int = 100) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT task_id, goal, created_at FROM scripts ORDER BY updated_at DESC LIMIT ?", (limit,))
        return [{"task_id": r["task_id"], "goal": r["goal"], "created_at": r["created_at"]} for r in cur.fetchall()]

    def script_delete(self, task_id: str) -> bool:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM scripts WHERE task_id = ?", (task_id,))
        self.conn.commit()
        return cur.rowcount > 0

    # --- TrajectoryStore ---
    def trajectory_save(
        self,
        *,
        task_id: str,
        goal: str,
        operations: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        now = datetime.utcnow().isoformat() + "Z"
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO trajectories (task_id, goal, operations, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, goal, _json_serializer(operations), _json_serializer(metadata or {}), now),
        )
        self.conn.commit()
        return cur.lastrowid

    def trajectory_load(self, trajectory_id: int) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT id, task_id, goal, operations, metadata, created_at FROM trajectories WHERE id = ?", (trajectory_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "task_id": row["task_id"],
            "goal": row["goal"],
            "operations": _json_deserializer(row["operations"]),
            "metadata": _json_deserializer(row["metadata"]),
            "created_at": row["created_at"],
        }

    def trajectory_load_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load latest trajectory with given task_id."""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, task_id, goal, operations, metadata, created_at FROM trajectories WHERE task_id = ? ORDER BY id DESC LIMIT 1",
            (task_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "task_id": row["task_id"],
            "goal": row["goal"],
            "operations": _json_deserializer(row["operations"]),
            "metadata": _json_deserializer(row["metadata"]),
            "created_at": row["created_at"],
        }

    def trajectory_list(self, limit: int = 100) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT id, task_id, goal, created_at FROM trajectories ORDER BY id DESC LIMIT ?", (limit,))
        return [{"id": r["id"], "task_id": r["task_id"], "goal": r["goal"], "created_at": r["created_at"]} for r in cur.fetchall()]

    def trajectory_delete(self, trajectory_id: int) -> bool:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM trajectories WHERE id = ?", (trajectory_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def trajectory_delete_by_task_id(self, task_id: str) -> int:
        """Delete all trajectories with given task_id. Returns number deleted."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM trajectories WHERE task_id = ?", (task_id,))
        self.conn.commit()
        return cur.rowcount

    # --- SessionStore ---
    def session_start(
        self,
        session_id: str,
        *,
        task_id: Optional[str] = None,
        session_type: str = "replay",
    ) -> None:
        now = datetime.utcnow().isoformat() + "Z"
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO session_headers (session_id, task_id, session_type, created_at) VALUES (?, ?, ?, ?)",
            (session_id, task_id, session_type, now),
        )
        self.conn.commit()

    def session_append(
        self,
        session_id: str,
        *,
        step_index: int,
        action: str,
        selector: Optional[str] = None,
        url: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.utcnow().isoformat() + "Z"
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO session_steps (session_id, step_index, action, selector, url, timestamp, payload) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, step_index, action, selector, url, now, _json_serializer(payload or {})),
        )
        self.conn.commit()

    def session_get(self, session_id: str) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT step_index, action, selector, url, timestamp, payload FROM session_steps WHERE session_id = ? ORDER BY step_index",
            (session_id,),
        )
        return [
            {
                "step_index": r["step_index"],
                "action": r["action"],
                "selector": r["selector"],
                "url": r["url"],
                "timestamp": r["timestamp"],
                "payload": _json_deserializer(r["payload"]),
            }
            for r in cur.fetchall()
        ]

    def session_list(self, limit: int = 100) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT session_id, task_id, session_type, created_at FROM session_headers ORDER BY created_at DESC LIMIT ?", (limit,))
        return [
            {"session_id": r["session_id"], "task_id": r["task_id"], "session_type": r["session_type"], "created_at": r["created_at"]}
            for r in cur.fetchall()
        ]
