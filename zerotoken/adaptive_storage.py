"""
Adaptive element fingerprint storage (SQLite).
Stores and loads fingerprints by (domain, identifier) for adaptive relocation.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


class AdaptiveStorage:
    """SQLite storage for element fingerprints keyed by (domain, identifier)."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = str(Path.cwd() / "zerotoken_adaptive.db")
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fingerprints (
                    domain TEXT NOT NULL,
                    identifier TEXT NOT NULL,
                    fingerprint_json TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (domain, identifier)
                )
                """
            )

    def save(self, domain: str, identifier: str, fingerprint_dict: Dict[str, Any]) -> None:
        """Save or overwrite fingerprint for (domain, identifier)."""
        import time
        updated_at = time.time()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO fingerprints (domain, identifier, fingerprint_json, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (domain, identifier, json.dumps(fingerprint_dict, ensure_ascii=False), updated_at),
            )

    def load(self, domain: str, identifier: str) -> Optional[Dict[str, Any]]:
        """Load fingerprint for (domain, identifier). Returns None if not found."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT fingerprint_json FROM fingerprints WHERE domain = ? AND identifier = ?",
                (domain, identifier),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["fingerprint_json"])

    def delete(self, domain: str, identifier: str) -> bool:
        """Remove fingerprint for (domain, identifier). Returns True if a row was deleted."""
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "DELETE FROM fingerprints WHERE domain = ? AND identifier = ?",
                (domain, identifier),
            )
            return cur.rowcount > 0
