"""SQLite store for the news cache.

We share the same database as :mod:`market_identity` (single file
``data/app/market_bot.db``) so the news table participates in foreign keys
where useful. The schema is created lazily — calling :func:`ensure_news_schema`
is idempotent.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

# Re-use the identity package's connection helper so we share the DB file and
# its pragmas (foreign_keys ON, row_factory, transaction handling).
from market_identity.store import connection  # noqa: F401  (re-exported)


SCHEMA = """
CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    source TEXT,
    summary TEXT,
    sentiment REAL,
    impact_category TEXT,
    confidence REAL,
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    UNIQUE(ticker, url) ON CONFLICT REPLACE
);

CREATE INDEX IF NOT EXISTS idx_news_ticker ON news_items(ticker);
CREATE INDEX IF NOT EXISTS idx_news_published_at ON news_items(published_at);
"""


def ensure_news_schema() -> None:
    with connection() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def news_connection() -> Iterator:
    """Convenience wrapper that yields a connection with the schema ensured."""
    ensure_news_schema()
    with connection() as conn:
        yield conn


def _row_to_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}


def upsert_news_items(items: list[dict]) -> None:
    if not items:
        return
    ensure_news_schema()
    now_iso = datetime.utcnow().isoformat()
    with connection() as conn:
        for item in items:
            conn.execute(
                """
                INSERT INTO news_items (
                    ticker, title, url, source, summary, sentiment,
                    impact_category, confidence, published_at, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, url) DO UPDATE SET
                    title = excluded.title,
                    source = excluded.source,
                    summary = excluded.summary,
                    sentiment = excluded.sentiment,
                    impact_category = excluded.impact_category,
                    confidence = excluded.confidence,
                    published_at = excluded.published_at,
                    fetched_at = excluded.fetched_at
                """,
                (
                    item["ticker"].upper(),
                    item["title"],
                    item.get("url"),
                    item.get("source"),
                    item.get("summary"),
                    item.get("sentiment"),
                    item.get("impact_category"),
                    item.get("confidence"),
                    (item.get("published_at") or "")[:19] or None,
                    item.get("fetched_at", now_iso),
                ),
            )


def list_news_for_ticker(ticker: str, limit: int = 12) -> list[dict]:
    ensure_news_schema()
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT ticker, title, url, source, summary, sentiment,
                   impact_category, confidence, published_at, fetched_at
            FROM news_items
            WHERE ticker = ?
            ORDER BY COALESCE(published_at, fetched_at) DESC
            LIMIT ?
            """,
            (ticker.upper(), limit),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def latest_fetch_at(ticker: str) -> datetime | None:
    ensure_news_schema()
    with connection() as conn:
        row = conn.execute(
            "SELECT MAX(fetched_at) FROM news_items WHERE ticker = ?",
            (ticker.upper(),),
        ).fetchone()
    if not row or not row[0]:
        return None
    try:
        return datetime.fromisoformat(row[0])
    except ValueError:
        return None
