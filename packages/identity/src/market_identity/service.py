from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta

from .models import AuthenticatedUser, InvestorProfile, UserSession
from .store import connection, ensure_identity_schema


class IdentityError(RuntimeError):
    """Raised when auth or profile operations cannot be completed."""


class IdentityService:
    def __init__(self) -> None:
        ensure_identity_schema()

    def register_user(
        self,
        username: str,
        password: str,
        display_name: str | None = None,
        investor_profile: str = "moderate",
        preferred_horizon: str = "mixed",
        preferred_instrument_types: str = "both",
        risk_tolerance: str = "medium",
        benchmark_preference: str = "mep",
    ) -> UserSession:
        normalized_username = self._normalize_username(username)
        self._validate_password(password)
        now = datetime.utcnow()
        password_hash, password_salt = _hash_password(password)

        with connection() as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?",
                (normalized_username,),
            ).fetchone()
            if existing is not None:
                raise IdentityError("El username ya existe.")

            conn.execute(
                """
                INSERT INTO users (
                    username,
                    password_hash,
                    password_salt,
                    display_name,
                    local_currency,
                    investor_profile,
                    preferred_horizon,
                    preferred_instrument_types,
                    risk_tolerance,
                    benchmark_preference,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, 'ARS', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_username,
                    password_hash,
                    password_salt,
                    (display_name or normalized_username).strip(),
                    investor_profile,
                    preferred_horizon,
                    preferred_instrument_types,
                    risk_tolerance,
                    benchmark_preference,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            user_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

        return self._create_session(user_id)

    def login_user(self, username: str, password: str) -> UserSession:
        normalized_username = self._normalize_username(username)
        with connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (normalized_username,),
            ).fetchone()
        if row is None:
            raise IdentityError("Credenciales invalidas.")

        if not _verify_password(password, row["password_salt"], row["password_hash"]):
            raise IdentityError("Credenciales invalidas.")

        return self._create_session(int(row["id"]))

    def authenticate(self, access_token: str) -> AuthenticatedUser:
        token = access_token.strip()
        if not token:
            raise IdentityError("Token ausente.")
        token_hash = _token_digest(token)
        now = datetime.utcnow().isoformat()
        with connection() as conn:
            row = conn.execute(
                """
                SELECT users.id, users.username
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ?
                  AND sessions.expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
        if row is None:
            raise IdentityError("Sesion invalida o expirada.")
        return AuthenticatedUser(user_id=int(row["id"]), username=str(row["username"]))

    def logout(self, access_token: str) -> None:
        token = access_token.strip()
        if not token:
            return
        token_hash = _token_digest(token)
        with connection() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    def get_profile(self, user_id: int) -> InvestorProfile:
        with connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise IdentityError("Usuario no encontrado.")
        return _profile_from_row(row)

    def update_profile(
        self,
        user_id: int,
        display_name: str,
        investor_profile: str,
        preferred_horizon: str,
        preferred_instrument_types: str,
        risk_tolerance: str,
        benchmark_preference: str,
    ) -> InvestorProfile:
        now = datetime.utcnow().isoformat()
        with connection() as conn:
            conn.execute(
                """
                UPDATE users
                SET display_name = ?,
                    investor_profile = ?,
                    preferred_horizon = ?,
                    preferred_instrument_types = ?,
                    risk_tolerance = ?,
                    benchmark_preference = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    display_name.strip(),
                    investor_profile,
                    preferred_horizon,
                    preferred_instrument_types,
                    risk_tolerance,
                    benchmark_preference,
                    now,
                    user_id,
                ),
            )
        return self.get_profile(user_id)

    def _create_session(self, user_id: int) -> UserSession:
        profile = self.get_profile(user_id)
        access_token = secrets.token_urlsafe(32)
        token_hash = _token_digest(access_token)
        now = datetime.utcnow()
        expires_at = now + timedelta(days=30)
        with connection() as conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.execute(
                """
                INSERT INTO sessions (user_id, token_hash, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, token_hash, now.isoformat(), expires_at.isoformat()),
            )
        return UserSession(access_token=access_token, expires_at=expires_at, profile=profile)

    def _normalize_username(self, username: str) -> str:
        normalized = username.strip().lower()
        if len(normalized) < 3:
            raise IdentityError("El username debe tener al menos 3 caracteres.")
        return normalized

    def _validate_password(self, password: str) -> None:
        if len(password) < 6:
            raise IdentityError("La password debe tener al menos 6 caracteres.")


def _hash_password(password: str) -> tuple[str, str]:
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return derived.hex(), salt.hex()


def _verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        120_000,
    )
    return hmac.compare_digest(derived.hex(), expected_hash_hex)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _profile_from_row(row) -> InvestorProfile:
    return InvestorProfile(
        user_id=int(row["id"]),
        username=str(row["username"]),
        display_name=str(row["display_name"]),
        local_currency=str(row["local_currency"]),
        investor_profile=str(row["investor_profile"]),
        preferred_horizon=str(row["preferred_horizon"]),
        preferred_instrument_types=str(row["preferred_instrument_types"]),
        risk_tolerance=str(row["risk_tolerance"]),
        benchmark_preference=str(row["benchmark_preference"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
    )
