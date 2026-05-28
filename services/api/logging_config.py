"""Structured logging + request-id middleware.

Production wants one line per request with enough info to debug without
dumping payloads. We pick stdlib ``logging`` over ``loguru`` to avoid an
extra dependency.

Two pieces:

1. :class:`JsonFormatter` — turns each ``LogRecord`` into a single JSON
   line.
2. :func:`install_request_logging` — registers an ASGI middleware that
   assigns a request-id, times the request, and emits one JSON log line.

Errors are *not* swallowed here. If a handler raises, the middleware logs
the failure and re-raises so FastAPI's exception handlers still produce the
right HTTP response.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Callable

from starlette.types import ASGIApp, Receive, Scope, Send


_LOGGER_NAME = "market_bot.api"


class JsonFormatter(logging.Formatter):
    """Emit each log record as a compact JSON line."""

    _STD_RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Surface any ``extra={...}`` fields the caller passed in.
        for key, value in record.__dict__.items():
            if key in self._STD_RESERVED or key.startswith("_"):
                continue
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                value = str(value)
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logger() -> logging.Logger:
    """Configure ``market_bot.api`` logger to emit JSON to stderr.

    Idempotent — safe to call from ``app.py`` at import time.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    if any(getattr(handler, "_market_bot_json", False) for handler in logger.handlers):
        return logger
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler._market_bot_json = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


class RequestLoggingMiddleware:
    """ASGI middleware that logs one JSON line per HTTP request.

    Attaches a request-id to ``scope["state"]`` so downstream handlers can
    pick it up via ``request.state.request_id``.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = configure_logger()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        status_code = {"code": 500}
        start = time.perf_counter()

        async def _send(message: dict) -> None:
            if message["type"] == "http.response.start":
                status_code["code"] = int(message.get("status", 500))
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        method = scope.get("method", "?")
        path = scope.get("path", "?")
        try:
            await self.app(scope, receive, _send)
        except Exception:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            self.logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status": 500,
                    "latency_ms": elapsed_ms,
                },
            )
            raise
        else:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            self.logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status": status_code["code"],
                    "latency_ms": elapsed_ms,
                },
            )


def install_request_logging(app) -> None:
    """Attach the request-logging middleware to a FastAPI app."""
    app.add_middleware(RequestLoggingMiddleware)
    configure_logger()


# ---------------------------------------------------------------------------
# Rate limiting — minimal in-memory token bucket
# ---------------------------------------------------------------------------
#
# We don't pull ``slowapi`` because (a) it adds a dependency, and (b) the
# rate limits we care about are coarse and per-route. This bucket lives
# in-process — fine for a single-host SQLite app. If/when the API runs
# behind multiple workers, swap this for Redis-backed slowapi.

from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status


_RateBucket = deque[float]
_BUCKETS: dict[str, dict[str, _RateBucket]] = defaultdict(lambda: defaultdict(deque))
_FAILURE_BUCKETS: dict[str, dict[str, _RateBucket]] = defaultdict(lambda: defaultdict(deque))
_LOCK = Lock()


def rate_limit(*, key: str, max_hits: int, window_seconds: int) -> Callable:
    """FastAPI dependency factory that enforces ``max_hits / window_seconds`` per IP.

    The window is sliding (newest hit drops the oldest), so bursts are not
    permitted. The ``key`` namespaces multiple limiters (e.g. one for
    ``/auth/login`` and another for ``/auth/register``).
    """

    def _dependency(request: Request) -> None:
        client = request.client.host if request.client else "anonymous"
        now = time.monotonic()
        cutoff = now - window_seconds
        with _LOCK:
            bucket = _BUCKETS[key][client]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= max_hits:
                retry_after = max(1, int(window_seconds - (now - bucket[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit excedido. Volve a intentar en unos segundos.",
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(now)

    return _dependency


def _client_host(request: Request) -> str:
    return request.client.host if request.client else "anonymous"


def _auth_subject(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized or "__anonymous__"


def auth_failure_retry_after(
    *,
    key: str,
    request: Request,
    subject: str | None,
    max_hits: int,
    window_seconds: int,
) -> int | None:
    client = _client_host(request)
    bucket_key = f"{client}:{_auth_subject(subject)}"
    now = time.monotonic()
    cutoff = now - window_seconds
    with _LOCK:
        bucket = _FAILURE_BUCKETS[key][bucket_key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) < max_hits:
            return None
        return max(1, int(window_seconds - (now - bucket[0])))


def record_auth_failure(*, key: str, request: Request, subject: str | None) -> None:
    client = _client_host(request)
    bucket_key = f"{client}:{_auth_subject(subject)}"
    now = time.monotonic()
    with _LOCK:
        _FAILURE_BUCKETS[key][bucket_key].append(now)


def clear_auth_failures(*, key: str, request: Request, subject: str | None) -> None:
    client = _client_host(request)
    bucket_key = f"{client}:{_auth_subject(subject)}"
    with _LOCK:
        if key in _FAILURE_BUCKETS:
            _FAILURE_BUCKETS[key].pop(bucket_key, None)


def reset_rate_buckets() -> None:
    """Test helper — wipe the in-memory bucket state."""
    with _LOCK:
        _BUCKETS.clear()
        _FAILURE_BUCKETS.clear()
