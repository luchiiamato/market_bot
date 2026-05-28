"""Decision audit log.

Persists each user-confirmed decision (e.g. "I bought AAPL based on this
analysis") alongside the full analysis snapshot at decision time. Two
purposes:

1. Calibration: replay later (after 30/60/90 days) to compute realised return
   vs predicted scenarios. Feeds the validation module (Sprint 3b).
2. Product analytics: which recommendations does the user actually act on?
   Are they buying the high-conviction ones or the contrarian ones?

We use a separate module from :mod:`market_identity.store` (which keeps the
``users``/``sessions`` schema) but share the same SQLite database via the
common :func:`connection` helper.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from .store import connection


SCHEMA = """
CREATE TABLE IF NOT EXISTS user_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    horizon TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    conviction REAL,
    rationale TEXT,
    analysis_snapshot_json TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    realized_return REAL,
    realized_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_decisions_user_id ON user_decisions(user_id);
CREATE INDEX IF NOT EXISTS idx_decisions_ticker ON user_decisions(ticker);
CREATE INDEX IF NOT EXISTS idx_decisions_decided_at ON user_decisions(decided_at);
"""


class DecisionStoreError(RuntimeError):
    """Raised when a decision cannot be persisted or fetched."""


@dataclass
class DecisionRecord:
    decision_id: int
    user_id: int
    ticker: str
    horizon: str
    action_taken: str
    conviction: float | None
    rationale: str | None
    analysis_snapshot: dict[str, Any]
    decided_at: datetime
    realized_return: float | None
    realized_at: datetime | None


def ensure_decisions_schema() -> None:
    with connection() as conn:
        conn.executescript(SCHEMA)


def record_decision(
    user_id: int,
    ticker: str,
    horizon: str,
    action_taken: str,
    analysis_snapshot: dict[str, Any],
    conviction: float | None = None,
    rationale: str | None = None,
) -> DecisionRecord:
    """Persist a decision with the full analysis snapshot.

    ``analysis_snapshot`` is serialised to JSON. The caller is responsible for
    handing us a dict (re-execute :meth:`MarketBotService.analyze_ticker` and
    dump it — never trust the client to send the snapshot).
    """
    ensure_decisions_schema()
    decided_at = datetime.utcnow().isoformat()
    snapshot_json = json.dumps(analysis_snapshot, default=_json_default)
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO user_decisions (
                user_id, ticker, horizon, action_taken, conviction, rationale,
                analysis_snapshot_json, decided_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                ticker.upper(),
                horizon,
                action_taken,
                conviction,
                rationale,
                snapshot_json,
                decided_at,
            ),
        )
        decision_id = int(cursor.lastrowid or 0)
    return DecisionRecord(
        decision_id=decision_id,
        user_id=user_id,
        ticker=ticker.upper(),
        horizon=horizon,
        action_taken=action_taken,
        conviction=conviction,
        rationale=rationale,
        analysis_snapshot=analysis_snapshot,
        decided_at=datetime.fromisoformat(decided_at),
        realized_return=None,
        realized_at=None,
    )


def list_decisions(
    user_id: int,
    *,
    since: date | None = None,
    ticker: str | None = None,
    limit: int = 100,
) -> list[DecisionRecord]:
    ensure_decisions_schema()
    where = ["user_id = ?"]
    params: list[Any] = [user_id]
    if since is not None:
        where.append("decided_at >= ?")
        params.append(since.isoformat())
    if ticker is not None:
        where.append("ticker = ?")
        params.append(ticker.upper())
    params.append(limit)
    with connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, user_id, ticker, horizon, action_taken, conviction, rationale,
                   analysis_snapshot_json, decided_at, realized_return, realized_at
            FROM user_decisions
            WHERE {" AND ".join(where)}
            ORDER BY decided_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [_row_to_record(row) for row in rows]


def update_realized_return(decision_id: int, realized_return: float) -> None:
    ensure_decisions_schema()
    realized_at = datetime.utcnow().isoformat()
    with connection() as conn:
        conn.execute(
            "UPDATE user_decisions SET realized_return = ?, realized_at = ? WHERE id = ?",
            (realized_return, realized_at, decision_id),
        )


def _row_to_record(row) -> DecisionRecord:
    try:
        snapshot = json.loads(row["analysis_snapshot_json"]) if row["analysis_snapshot_json"] else {}
    except json.JSONDecodeError:
        snapshot = {}
    realized_at = row["realized_at"]
    return DecisionRecord(
        decision_id=int(row["id"]),
        user_id=int(row["user_id"]),
        ticker=str(row["ticker"]),
        horizon=str(row["horizon"]),
        action_taken=str(row["action_taken"]),
        conviction=float(row["conviction"]) if row["conviction"] is not None else None,
        rationale=str(row["rationale"]) if row["rationale"] else None,
        analysis_snapshot=snapshot,
        decided_at=datetime.fromisoformat(str(row["decided_at"])),
        realized_return=float(row["realized_return"]) if row["realized_return"] is not None else None,
        realized_at=datetime.fromisoformat(str(realized_at)) if realized_at else None,
    )


def _json_default(obj: Any) -> Any:
    """JSON encoder fallback for dataclass-laden analysis snapshots."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "value"):  # Enum
        return obj.value
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)
