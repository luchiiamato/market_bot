"""SQLite persistence for chat threads + messages.

Shares the identity DB connection (via :func:`market_identity.store.connection`)
so we don't open a second file. Two tables:

* ``chat_threads`` — one row per conversation.
* ``chat_messages`` — every turn, including audit fields (tokens, cost,
  latency) used by ``GET /chat/usage``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from market_identity.store import connection


SYSTEM_PROMPT_BASELINE = (
    "Sos el asistente de Market Bot, una terminal de inversión para usuarios de Argentina. "
    "Respondés en español, con tono claro, corto y técnico. "
    "Solo ayudás con: portfolio, CEDEARs, stocks, análisis técnico, métricas fundamentales, "
    "earnings, benchmarks argentinos, noticias de mercado y conceptos financieros. "
    "Si te preguntan algo fuera de ese dominio, redirigí en una sola frase al alcance de la herramienta. "
    "No des consejos financieros personalizados ni órdenes directas de compra/venta. "
    "Si te preguntan 'qué hago', respondé con marco de decisión, riesgos, datos a mirar y trade-offs. "
    "Preferí bullets cortos cuando expliqués varios puntos. "
    "No inventes datos, precios ni hechos; si falta contexto, decilo explícitamente."
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_threads_user_id ON chat_threads(user_id);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(thread_id) REFERENCES chat_threads(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_id ON chat_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);
"""


@dataclass
class ChatThread:
    id: int
    user_id: int
    title: str
    provider: str | None
    model: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class ChatMessageRow:
    id: int
    thread_id: int
    role: str
    content: str
    provider: str | None
    model: str | None
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    created_at: datetime


def ensure_chat_schema() -> None:
    with connection() as conn:
        conn.executescript(SCHEMA)


def create_thread(
    user_id: int,
    title: str,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> ChatThread:
    ensure_chat_schema()
    now = datetime.utcnow().isoformat()
    clean_title = _clean_thread_title(title)
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO chat_threads (user_id, title, provider, model, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, clean_title, provider, model, now, now),
        )
        thread_id = int(cursor.lastrowid or 0)
    return ChatThread(
        id=thread_id,
        user_id=user_id,
        title=clean_title,
        provider=provider,
        model=model,
        created_at=datetime.fromisoformat(now),
        updated_at=datetime.fromisoformat(now),
    )


def list_threads(user_id: int) -> list[ChatThread]:
    ensure_chat_schema()
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, title, provider, model, created_at, updated_at
            FROM chat_threads
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [_row_to_thread(row) for row in rows]


def get_thread(thread_id: int, user_id: int) -> ChatThread | None:
    ensure_chat_schema()
    with connection() as conn:
        row = conn.execute(
            """
            SELECT id, user_id, title, provider, model, created_at, updated_at
            FROM chat_threads
            WHERE id = ? AND user_id = ?
            """,
            (thread_id, user_id),
        ).fetchone()
    return _row_to_thread(row) if row else None


def update_thread_title(thread_id: int, user_id: int, title: str) -> ChatThread | None:
    ensure_chat_schema()
    now = datetime.utcnow().isoformat()
    clean_title = _clean_thread_title(title)
    with connection() as conn:
        cursor = conn.execute(
            """
            UPDATE chat_threads
            SET title = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (clean_title, now, thread_id, user_id),
        )
        if cursor.rowcount == 0:
            return None
    return get_thread(thread_id, user_id)


def delete_thread(thread_id: int, user_id: int) -> bool:
    ensure_chat_schema()
    with connection() as conn:
        cursor = conn.execute(
            "DELETE FROM chat_threads WHERE id = ? AND user_id = ?",
            (thread_id, user_id),
        )
    return bool(cursor.rowcount)


def append_message(
    thread_id: int,
    role: str,
    content: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    latency_ms: int = 0,
) -> ChatMessageRow:
    ensure_chat_schema()
    now = datetime.utcnow().isoformat()
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO chat_messages (
                thread_id, role, content, provider, model,
                tokens_in, tokens_out, cost_usd, latency_ms, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                thread_id,
                role,
                content,
                provider,
                model,
                int(tokens_in or 0),
                int(tokens_out or 0),
                float(cost_usd or 0.0),
                int(latency_ms or 0),
                now,
            ),
        )
        message_id = int(cursor.lastrowid or 0)
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (now, thread_id),
        )
    return ChatMessageRow(
        id=message_id,
        thread_id=thread_id,
        role=role,
        content=content,
        provider=provider,
        model=model,
        tokens_in=int(tokens_in or 0),
        tokens_out=int(tokens_out or 0),
        cost_usd=float(cost_usd or 0.0),
        latency_ms=int(latency_ms or 0),
        created_at=datetime.fromisoformat(now),
    )


def list_messages(thread_id: int, user_id: int) -> list[ChatMessageRow]:
    """Return messages for a thread iff it belongs to ``user_id``.

    Returns an empty list if the thread is missing or owned by someone else —
    callers can distinguish "no messages" from "no access" via :func:`get_thread`.
    """

    if get_thread(thread_id, user_id) is None:
        return []
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT id, thread_id, role, content, provider, model,
                   tokens_in, tokens_out, cost_usd, latency_ms, created_at
            FROM chat_messages
            WHERE thread_id = ?
            ORDER BY id ASC
            """,
            (thread_id,),
        ).fetchall()
    return [_row_to_message(row) for row in rows]


def usage_for_user(user_id: int) -> dict[str, Any]:
    """Aggregate spend per provider + per day/month for ``user_id``.

    Used by ``GET /chat/usage`` (Sprint 8.5 cost tracking).
    """

    ensure_chat_schema()
    with connection() as conn:
        by_provider = conn.execute(
            """
            SELECT m.provider AS provider,
                   COALESCE(SUM(m.tokens_in), 0) AS tokens_in,
                   COALESCE(SUM(m.tokens_out), 0) AS tokens_out,
                   COALESCE(SUM(m.cost_usd), 0.0) AS cost_usd,
                   COUNT(m.id) AS message_count
            FROM chat_messages m
            JOIN chat_threads t ON t.id = m.thread_id
            WHERE t.user_id = ? AND m.provider IS NOT NULL
            GROUP BY m.provider
            ORDER BY cost_usd DESC
            """,
            (user_id,),
        ).fetchall()

        totals = conn.execute(
            """
            SELECT COALESCE(SUM(m.tokens_in), 0) AS tokens_in,
                   COALESCE(SUM(m.tokens_out), 0) AS tokens_out,
                   COALESCE(SUM(m.cost_usd), 0.0) AS cost_usd,
                   COUNT(m.id) AS message_count
            FROM chat_messages m
            JOIN chat_threads t ON t.id = m.thread_id
            WHERE t.user_id = ?
            """,
            (user_id,),
        ).fetchone()

        # Daily / monthly slices via SQLite substr() on the ISO timestamp.
        today_iso = datetime.utcnow().date().isoformat()
        month_prefix = today_iso[:7]
        today_total = conn.execute(
            """
            SELECT COALESCE(SUM(m.cost_usd), 0.0) AS cost_usd
            FROM chat_messages m
            JOIN chat_threads t ON t.id = m.thread_id
            WHERE t.user_id = ? AND substr(m.created_at, 1, 10) = ?
            """,
            (user_id, today_iso),
        ).fetchone()
        month_total = conn.execute(
            """
            SELECT COALESCE(SUM(m.cost_usd), 0.0) AS cost_usd
            FROM chat_messages m
            JOIN chat_threads t ON t.id = m.thread_id
            WHERE t.user_id = ? AND substr(m.created_at, 1, 7) = ?
            """,
            (user_id, month_prefix),
        ).fetchone()

    return {
        "user_id": user_id,
        "total_tokens_in": int(totals["tokens_in"] or 0),
        "total_tokens_out": int(totals["tokens_out"] or 0),
        "total_cost_usd": float(totals["cost_usd"] or 0.0),
        "total_messages": int(totals["message_count"] or 0),
        "cost_today_usd": float(today_total["cost_usd"] or 0.0),
        "cost_month_usd": float(month_total["cost_usd"] or 0.0),
        "by_provider": [
            {
                "provider": str(row["provider"]),
                "tokens_in": int(row["tokens_in"] or 0),
                "tokens_out": int(row["tokens_out"] or 0),
                "cost_usd": float(row["cost_usd"] or 0.0),
                "message_count": int(row["message_count"] or 0),
            }
            for row in by_provider
        ],
    }


# ---------------------------------------------------------------------------
# Row → dataclass helpers
# ---------------------------------------------------------------------------


def _row_to_thread(row) -> ChatThread:
    return ChatThread(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        title=str(row["title"]),
        provider=str(row["provider"]) if row["provider"] else None,
        model=str(row["model"]) if row["model"] else None,
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )


def _clean_thread_title(title: str | None) -> str:
    return (title or "Nueva conversación").strip()[:120] or "Nueva conversación"


def _row_to_message(row) -> ChatMessageRow:
    return ChatMessageRow(
        id=int(row["id"]),
        thread_id=int(row["thread_id"]),
        role=str(row["role"]),
        content=str(row["content"]),
        provider=str(row["provider"]) if row["provider"] else None,
        model=str(row["model"]) if row["model"] else None,
        tokens_in=int(row["tokens_in"] or 0),
        tokens_out=int(row["tokens_out"] or 0),
        cost_usd=float(row["cost_usd"] or 0.0),
        latency_ms=int(row["latency_ms"] or 0),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )
