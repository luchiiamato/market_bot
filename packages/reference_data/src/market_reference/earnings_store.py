"""SQLite store for the earnings calendar."""

from __future__ import annotations

from datetime import date, datetime

from market_identity.store import connection


SCHEMA = """
CREATE TABLE IF NOT EXISTS earnings_calendar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    report_date TEXT NOT NULL,
    report_time TEXT,
    eps_estimate REAL,
    eps_actual REAL,
    revenue_estimate REAL,
    revenue_actual REAL,
    fetched_at TEXT NOT NULL,
    UNIQUE(ticker, report_date) ON CONFLICT REPLACE
);

CREATE INDEX IF NOT EXISTS idx_earnings_ticker ON earnings_calendar(ticker);
CREATE INDEX IF NOT EXISTS idx_earnings_report_date ON earnings_calendar(report_date);
"""


def ensure_earnings_schema() -> None:
    with connection() as conn:
        conn.executescript(SCHEMA)


def upsert_earnings(events: list[dict]) -> None:
    if not events:
        return
    ensure_earnings_schema()
    fetched_at = datetime.utcnow().isoformat()
    with connection() as conn:
        for event in events:
            conn.execute(
                """
                INSERT INTO earnings_calendar (
                    ticker, report_date, report_time, eps_estimate, eps_actual,
                    revenue_estimate, revenue_actual, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, report_date) DO UPDATE SET
                    report_time = excluded.report_time,
                    eps_estimate = excluded.eps_estimate,
                    eps_actual = excluded.eps_actual,
                    revenue_estimate = excluded.revenue_estimate,
                    revenue_actual = excluded.revenue_actual,
                    fetched_at = excluded.fetched_at
                """,
                (
                    event["ticker"].upper(),
                    event["report_date"],
                    event.get("report_time"),
                    event.get("eps_estimate"),
                    event.get("eps_actual"),
                    event.get("revenue_estimate"),
                    event.get("revenue_actual"),
                    event.get("fetched_at", fetched_at),
                ),
            )


def list_upcoming(tickers: list[str] | None = None, *, days_ahead: int = 60) -> list[dict]:
    ensure_earnings_schema()
    cutoff_iso = date.today().isoformat()
    with connection() as conn:
        if tickers:
            placeholders = ",".join("?" for _ in tickers)
            rows = conn.execute(
                f"""
                SELECT ticker, report_date, report_time, eps_estimate, eps_actual,
                       revenue_estimate, revenue_actual, fetched_at
                FROM earnings_calendar
                WHERE ticker IN ({placeholders})
                  AND report_date >= ?
                ORDER BY report_date ASC
                """,
                (*[t.upper() for t in tickers], cutoff_iso),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT ticker, report_date, report_time, eps_estimate, eps_actual,
                       revenue_estimate, revenue_actual, fetched_at
                FROM earnings_calendar
                WHERE report_date >= ?
                ORDER BY report_date ASC
                LIMIT 200
                """,
                (cutoff_iso,),
            ).fetchall()

    out: list[dict] = []
    for row in rows:
        report_date = str(row["report_date"])
        try:
            parsed_date = date.fromisoformat(report_date[:10])
        except ValueError:
            continue
        if (parsed_date - date.today()).days > days_ahead:
            continue
        out.append({key: row[key] for key in row.keys()})
    return out


def next_earnings_date(ticker: str) -> date | None:
    """Return the next future earnings date for ``ticker`` or ``None``."""
    upcoming = list_upcoming([ticker], days_ahead=400)
    if not upcoming:
        return None
    try:
        return date.fromisoformat(str(upcoming[0]["report_date"])[:10])
    except ValueError:
        return None


def latest_fetch_at(ticker: str) -> datetime | None:
    ensure_earnings_schema()
    with connection() as conn:
        row = conn.execute(
            "SELECT MAX(fetched_at) FROM earnings_calendar WHERE ticker = ?",
            (ticker.upper(),),
        ).fetchone()
    if not row or not row[0]:
        return None
    try:
        return datetime.fromisoformat(row[0])
    except ValueError:
        return None
