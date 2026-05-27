from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


ROOT_DIR = Path(__file__).resolve().parents[5]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "app" / "market_bot.db"


def database_path() -> Path:
    raw_path = os.getenv("MARKET_BOT_DB_PATH")
    if raw_path:
        return Path(raw_path).expanduser().resolve()
    return DEFAULT_DB_PATH


def ensure_identity_schema() -> None:
    db_path = database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                display_name TEXT NOT NULL,
                local_currency TEXT NOT NULL DEFAULT 'ARS',
                investor_profile TEXT NOT NULL DEFAULT 'moderate',
                preferred_horizon TEXT NOT NULL DEFAULT 'mixed',
                preferred_instrument_types TEXT NOT NULL DEFAULT 'both',
                risk_tolerance TEXT NOT NULL DEFAULT 'medium',
                benchmark_preference TEXT NOT NULL DEFAULT 'mep',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash);
            """
        )


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    db_path = database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
