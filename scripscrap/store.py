"""SQLite storage for named scrape sources and their latest tables."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path("data") / "scripscrap.db"


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Store:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    table_index INTEGER,
                    timeout REAL NOT NULL DEFAULT 30,
                    created_at TEXT NOT NULL,
                    last_run_at TEXT,
                    last_error TEXT,
                    row_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    source_id INTEGER PRIMARY KEY
                        REFERENCES sources(id) ON DELETE CASCADE,
                    tables_json TEXT NOT NULL,
                    scraped_at TEXT NOT NULL
                );
                """
            )

    def list_sources(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sources ORDER BY last_run_at IS NULL, last_run_at DESC, id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_source(self, source_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
        return dict(row) if row else None

    def add_source(
        self,
        *,
        name: str,
        url: str,
        table_index: int | None,
        timeout: float,
    ) -> int:
        now = utcnow()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO sources (name, url, table_index, timeout, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, url, table_index, timeout, now),
            )
            return int(cursor.lastrowid)

    def update_source(
        self,
        source_id: int,
        *,
        name: str,
        url: str,
        table_index: int | None,
        timeout: float,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE sources
                SET name = ?, url = ?, table_index = ?, timeout = ?
                WHERE id = ?
                """,
                (name, url, table_index, timeout, source_id),
            )

    def delete_source(self, source_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))

    def save_snapshot(
        self,
        source_id: int,
        tables: list[dict[str, Any]],
    ) -> None:
        now = utcnow()
        row_count = sum(len(table.get("rows") or []) for table in tables)
        payload = json.dumps(tables)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO snapshots (source_id, tables_json, scraped_at)
                VALUES (?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    tables_json = excluded.tables_json,
                    scraped_at = excluded.scraped_at
                """,
                (source_id, payload, now),
            )
            conn.execute(
                """
                UPDATE sources
                SET last_run_at = ?, last_error = NULL, row_count = ?
                WHERE id = ?
                """,
                (now, row_count, source_id),
            )

    def save_error(self, source_id: int, message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE sources
                SET last_run_at = ?, last_error = ?
                WHERE id = ?
                """,
                (utcnow(), message, source_id),
            )

    def get_snapshot(self, source_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE source_id = ?", (source_id,)
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["tables"] = json.loads(data.pop("tables_json"))
        return data
