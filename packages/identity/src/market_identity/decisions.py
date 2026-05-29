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
import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from .store import connection

logger = logging.getLogger("market_bot.api")

# Days after a decision before we consider it "mature" enough to realize.
HORIZON_MATURITY_DAYS: dict[str, int] = {
    "short": 7,
    "long": 30,
}


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


def get_pending_decisions() -> list[DecisionRecord]:
    """Return decisions across all users that are mature but not yet realized."""
    ensure_decisions_schema()
    cutoffs: list[tuple[str, str]] = [
        (horizon, (datetime.utcnow() - timedelta(days=days)).isoformat())
        for horizon, days in HORIZON_MATURITY_DAYS.items()
    ]
    rows: list[Any] = []
    with connection() as conn:
        for horizon, cutoff in cutoffs:
            rows.extend(
                conn.execute(
                    """
                    SELECT id, user_id, ticker, horizon, action_taken, conviction, rationale,
                           analysis_snapshot_json, decided_at, realized_return, realized_at
                    FROM user_decisions
                    WHERE realized_return IS NULL
                      AND horizon = ?
                      AND decided_at <= ?
                    ORDER BY decided_at ASC
                    LIMIT 500
                    """,
                    (horizon, cutoff),
                ).fetchall()
            )
    return [_row_to_record(row) for row in rows]


def realize_decisions_job() -> dict[str, int]:
    """Fetch historical prices for pending decisions and persist realized returns.

    Safe to call repeatedly — skips decisions that are already realized.
    Returns counts of {realized, skipped, errors}.
    """
    try:
        import yfinance as yf  # noqa: PLC0415
    except ModuleNotFoundError:
        logger.warning("realize_decisions_job: yfinance not installed, skipping")
        return {"realized": 0, "skipped": 0, "errors": 0}

    pending = get_pending_decisions()
    if not pending:
        return {"realized": 0, "skipped": 0, "errors": 0}

    realized = skipped = errors = 0
    for rec in pending:
        try:
            maturity = HORIZON_MATURITY_DAYS.get(rec.horizon.lower(), 7)
            decision_date = rec.decided_at.date()
            end_date = decision_date + timedelta(days=maturity + 5)  # +5 buffer for weekends
            if end_date > date.today():
                skipped += 1
                continue

            frame = yf.download(
                rec.ticker,
                start=decision_date.isoformat(),
                end=end_date.isoformat(),
                interval="1d",
                auto_adjust=True,
                progress=False,
            )
            if frame.empty or len(frame) < 2:
                skipped += 1
                continue
            try:
                import pandas as _pd  # noqa: PLC0415
                if isinstance(frame.columns, _pd.MultiIndex):
                    frame.columns = frame.columns.get_level_values(0)
            except Exception:
                pass

            price_at_decision = float(frame.iloc[0]["Close"])
            price_at_maturity = float(frame.iloc[-1]["Close"])
            if price_at_decision <= 0:
                skipped += 1
                continue

            ret = (price_at_maturity - price_at_decision) / price_at_decision
            update_realized_return(rec.decision_id, ret)
            realized += 1
        except Exception as exc:
            logger.warning("realize_decisions_job: error for decision %d: %s", rec.decision_id, exc)
            errors += 1

    logger.info(
        "realize_decisions_job done: realized=%d skipped=%d errors=%d",
        realized, skipped, errors,
    )
    return {"realized": realized, "skipped": skipped, "errors": errors}


@dataclass
class TrackRecord:
    n_realized: int
    n_pending: int
    hit_rate: float | None       # fraction of realized decisions with return > 0
    avg_return: float | None     # mean realized return
    sharpe: float | None         # avg / std if >= 3 data points
    best_ticker: str | None
    worst_ticker: str | None
    by_ticker: list[dict[str, Any]]


def compute_track_record(user_id: int) -> TrackRecord:
    """Aggregate realized decisions for a user into a track record."""
    ensure_decisions_schema()
    with connection() as conn:
        all_rows = conn.execute(
            """
            SELECT ticker, horizon, action_taken, realized_return, decided_at
            FROM user_decisions
            WHERE user_id = ?
            ORDER BY decided_at DESC
            """,
            (user_id,),
        ).fetchall()

    realized = [r for r in all_rows if r["realized_return"] is not None]
    pending = [r for r in all_rows if r["realized_return"] is None]

    if not realized:
        return TrackRecord(
            n_realized=0,
            n_pending=len(pending),
            hit_rate=None,
            avg_return=None,
            sharpe=None,
            best_ticker=None,
            worst_ticker=None,
            by_ticker=[],
        )

    returns = [float(r["realized_return"]) for r in realized]
    n = len(returns)
    avg = sum(returns) / n
    hits = sum(1 for r in returns if r > 0)

    sharpe: float | None = None
    if n >= 3:
        variance = sum((r - avg) ** 2 for r in returns) / (n - 1)
        std = math.sqrt(variance) if variance > 0 else 0.0
        sharpe = round(avg / std, 3) if std > 0 else None

    # Per-ticker aggregation
    from collections import defaultdict
    ticker_returns: dict[str, list[float]] = defaultdict(list)
    for r in realized:
        ticker_returns[str(r["ticker"])].append(float(r["realized_return"]))

    by_ticker = sorted(
        [
            {
                "ticker": t,
                "n": len(rets),
                "avg_return": round(sum(rets) / len(rets), 4),
                "hit_rate": round(sum(1 for r in rets if r > 0) / len(rets), 3),
            }
            for t, rets in ticker_returns.items()
        ],
        key=lambda x: x["avg_return"],
        reverse=True,
    )

    best = by_ticker[0]["ticker"] if by_ticker else None
    worst = by_ticker[-1]["ticker"] if by_ticker else None

    return TrackRecord(
        n_realized=n,
        n_pending=len(pending),
        hit_rate=round(hits / n, 3),
        avg_return=round(avg, 4),
        sharpe=sharpe,
        best_ticker=best,
        worst_ticker=worst,
        by_ticker=by_ticker,
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
