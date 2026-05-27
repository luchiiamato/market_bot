from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: datetime


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int):
        self.ttl = timedelta(seconds=ttl_seconds)
        self._store: dict[object, CacheEntry[T]] = {}
        self._lock = RLock()

    def get(self, key: object) -> T | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if datetime.utcnow() >= entry.expires_at:
                self._store.pop(key, None)
                return None
            return entry.value

    def set(self, key: object, value: T) -> T:
        with self._lock:
            self._store[key] = CacheEntry(value=value, expires_at=datetime.utcnow() + self.ttl)
            return value
