"""Durable daily dashboard aggregates."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backend.paths import DATA_DIR

DB_PATH = Path(os.getenv("ANALYTICS_DB_PATH", str(DATA_DIR / "analytics.sqlite3")))


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("""CREATE TABLE IF NOT EXISTS daily_document_stats (
        day TEXT PRIMARY KEY,
        uploaded INTEGER NOT NULL DEFAULT 0,
        processed INTEGER NOT NULL DEFAULT 0
    )""")
    return connection


def _increment(column: str) -> None:
    if column not in {"uploaded", "processed"}:
        raise ValueError("unsupported analytics counter")
    day = datetime.now(timezone.utc).date().isoformat()
    with _connect() as connection:
        connection.execute(
            f"INSERT INTO daily_document_stats(day, {column}) VALUES (?, 1) "
            f"ON CONFLICT(day) DO UPDATE SET {column} = {column} + 1",
            (day,),
        )


def record_upload() -> None:
    _increment("uploaded")


def record_processed() -> None:
    _increment("processed")


def recent_activity(days: int = 30) -> list[dict]:
    with _connect() as connection:
        rows = connection.execute(
            "SELECT day, uploaded, processed FROM daily_document_stats ORDER BY day DESC LIMIT ?",
            (days,),
        ).fetchall()
    return [{"label": day, "uploaded": uploaded, "processed": processed}
            for day, uploaded, processed in reversed(rows)]
