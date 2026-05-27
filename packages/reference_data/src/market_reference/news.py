"""News ingestion adapter.

Strategy: yfinance ships a ``Ticker.news`` accessor that hits the same feed
Yahoo Finance uses on the web. It requires no API key, which fits the v1
"no external paid services" boundary. The optional Marketaux adapter is
wired behind ``MARKETAUX_API_KEY`` for richer sentiment scores; if absent
we fall back gracefully.

We persist into ``news_items`` with a stale-while-revalidate cache window
(``CACHE_TTL_SECONDS``). Every call to :func:`fetch_news` returns the freshest
view; whether it triggers a refetch depends on the last ``fetched_at``.

Sentiment + impact classification is intentionally lightweight: a keyword
scoring pass over the headline. This is **not** the place to add NLP — it's
enough to bias catalyst status downstream.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

import requests

from .news_store import (
    latest_fetch_at,
    list_news_for_ticker,
    upsert_news_items,
)


class NewsIngestionError(RuntimeError):
    """Raised when news ingestion cannot complete (network, auth, etc.)."""


CACHE_TTL_SECONDS = 2 * 60 * 60  # 2 hours — stale-while-revalidate window.

# Headline keyword scoring. Numbers are intentionally small; this is a bias,
# not a sentiment model.
POSITIVE_TERMS = {
    "beats": 0.4,
    "beat": 0.35,
    "raises": 0.3,
    "upgrade": 0.35,
    "buy": 0.25,
    "surge": 0.3,
    "soar": 0.35,
    "record": 0.25,
    "profit": 0.15,
    "growth": 0.15,
    "approves": 0.25,
    "wins": 0.25,
    "partnership": 0.15,
}
NEGATIVE_TERMS = {
    "miss": -0.35,
    "misses": -0.4,
    "cuts": -0.3,
    "downgrade": -0.35,
    "sell": -0.25,
    "plunge": -0.35,
    "tumble": -0.3,
    "drop": -0.2,
    "loss": -0.25,
    "lawsuit": -0.3,
    "fraud": -0.5,
    "probe": -0.3,
    "warns": -0.2,
    "recall": -0.25,
}

# Topic → impact category map. First match wins.
IMPACT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bearnings?\b|\beps\b|\bquarterly\b", re.I), "earnings"),
    (re.compile(r"\bmerger|acquisition|acquires?|deal\b", re.I), "m&a"),
    (re.compile(r"\bCEO\b|\bCFO\b|\bresign|appointed\b", re.I), "management"),
    (re.compile(r"\bFDA\b|\bSEC\b|\bregulator|antitrust\b", re.I), "regulatory"),
    (re.compile(r"\bguidance\b|\bforecast\b|\boutlook\b", re.I), "guidance"),
    (re.compile(r"\blawsuit|sued|settlement\b", re.I), "litigation"),
    (re.compile(r"\bdividend|buyback\b", re.I), "capital_return"),
)


@dataclass
class NewsItem:
    ticker: str
    title: str
    url: str | None
    source: str | None
    summary: str | None
    sentiment: float
    impact_category: str
    confidence: float
    published_at: str | None  # ISO 8601
    fetched_at: str


def _classify_impact(title: str) -> str:
    for pattern, label in IMPACT_PATTERNS:
        if pattern.search(title):
            return label
    return "general"


def _score_sentiment(title: str) -> float:
    lowered = title.lower()
    score = 0.0
    for term, weight in POSITIVE_TERMS.items():
        if term in lowered:
            score += weight
    for term, weight in NEGATIVE_TERMS.items():
        if term in lowered:
            score += weight
    # Clamp to [-1, 1].
    return max(-1.0, min(1.0, score))


def _source_confidence(source: str | None) -> float:
    """Heuristic credibility per outlet. Defaults to 0.55 — middle of the road.

    The numbers are not authoritative; they exist so :data:`confidence` reflects
    *something* downstream code can threshold on.
    """
    if not source:
        return 0.45
    lowered = source.lower()
    tier_a = ("reuters", "bloomberg", "wall street journal", "ft.com", "financial times", "associated press")
    tier_b = ("cnbc", "marketwatch", "barron", "yahoo finance", "investor's business daily")
    tier_c = ("seeking alpha", "benzinga", "the motley fool", "zacks")
    if any(t in lowered for t in tier_a):
        return 0.85
    if any(t in lowered for t in tier_b):
        return 0.70
    if any(t in lowered for t in tier_c):
        return 0.55
    return 0.45


def _is_cache_fresh(ticker: str) -> bool:
    last = latest_fetch_at(ticker)
    if last is None:
        return False
    age = (datetime.utcnow() - last).total_seconds()
    return age < CACHE_TTL_SECONDS


def _fetch_yfinance_news(ticker: str) -> list[dict]:
    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:  # pragma: no cover - tested via mock
        raise NewsIngestionError("yfinance is required for news ingestion") from exc

    raw = []
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception as exc:  # pragma: no cover - network paths
        raise NewsIngestionError(f"yfinance news failed for {ticker}: {exc}") from exc

    items: list[dict] = []
    for entry in raw:
        # yfinance returns either a flat dict or a {"content": {...}} wrapper
        # depending on version. Normalise both shapes.
        content = entry.get("content") if isinstance(entry, dict) else None
        if content:
            title = content.get("title")
            url = (content.get("clickThroughUrl") or {}).get("url") or content.get("canonicalUrl", {}).get("url")
            source = (content.get("provider") or {}).get("displayName")
            published = content.get("pubDate")
            summary = content.get("summary")
        else:
            title = entry.get("title")
            url = entry.get("link")
            source = entry.get("publisher")
            published_ts = entry.get("providerPublishTime")
            published = (
                datetime.fromtimestamp(published_ts, tz=timezone.utc).isoformat()
                if published_ts
                else None
            )
            summary = entry.get("summary")

        if not title:
            continue

        items.append(
            {
                "title": title,
                "url": url,
                "source": source,
                "summary": summary,
                "published_at": published,
            }
        )
    return items


def _fetch_marketaux_news(ticker: str, api_key: str) -> list[dict]:  # pragma: no cover - integration
    try:
        response = requests.get(
            "https://api.marketaux.com/v1/news/all",
            params={
                "symbols": ticker,
                "filter_entities": "true",
                "language": "en",
                "limit": 12,
                "api_token": api_key,
            },
            timeout=8,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise NewsIngestionError(f"Marketaux fetch failed: {exc}") from exc

    payload = response.json() or {}
    items: list[dict] = []
    for entry in payload.get("data", []):
        items.append(
            {
                "title": entry.get("title"),
                "url": entry.get("url"),
                "source": entry.get("source"),
                "summary": entry.get("description"),
                "published_at": entry.get("published_at"),
            }
        )
    return items


def _classify_and_persist(ticker: str, raw_items: Iterable[dict]) -> list[NewsItem]:
    now = datetime.utcnow().isoformat()
    enriched: list[NewsItem] = []
    upsert_payload: list[dict] = []
    for raw in raw_items:
        title = raw.get("title") or ""
        if not title:
            continue
        sentiment = _score_sentiment(title)
        impact = _classify_impact(title)
        confidence = _source_confidence(raw.get("source"))
        item = NewsItem(
            ticker=ticker.upper(),
            title=title,
            url=raw.get("url"),
            source=raw.get("source"),
            summary=raw.get("summary"),
            sentiment=round(sentiment, 3),
            impact_category=impact,
            confidence=round(confidence, 3),
            published_at=raw.get("published_at"),
            fetched_at=now,
        )
        enriched.append(item)
        upsert_payload.append(
            {
                "ticker": item.ticker,
                "title": item.title,
                "url": item.url,
                "source": item.source,
                "summary": item.summary,
                "sentiment": item.sentiment,
                "impact_category": item.impact_category,
                "confidence": item.confidence,
                "published_at": item.published_at,
                "fetched_at": item.fetched_at,
            }
        )
    upsert_news_items(upsert_payload)
    return enriched


def fetch_news(ticker: str, *, force_refresh: bool = False) -> list[NewsItem]:
    """Return cached + freshly-fetched news for ``ticker``.

    Honors a 2h stale-while-revalidate window. Pass ``force_refresh=True`` to
    bypass it. Always returns the persisted view (so callers see whatever is
    most recent in DB even if the network fetch fails).
    """
    ticker = ticker.upper()
    if not force_refresh and _is_cache_fresh(ticker):
        return _read_from_store(ticker)

    api_key = os.getenv("MARKETAUX_API_KEY")
    raw_items: list[dict]
    try:
        if api_key:
            raw_items = _fetch_marketaux_news(ticker, api_key)
        else:
            raw_items = _fetch_yfinance_news(ticker)
    except NewsIngestionError:
        # Soft failure: serve whatever is in cache.
        return _read_from_store(ticker)

    _classify_and_persist(ticker, raw_items)
    return _read_from_store(ticker)


def _read_from_store(ticker: str) -> list[NewsItem]:
    rows = list_news_for_ticker(ticker)
    return [
        NewsItem(
            ticker=row["ticker"],
            title=row["title"],
            url=row.get("url"),
            source=row.get("source"),
            summary=row.get("summary"),
            sentiment=float(row["sentiment"] or 0.0),
            impact_category=row.get("impact_category") or "general",
            confidence=float(row["confidence"] or 0.0),
            published_at=row.get("published_at"),
            fetched_at=row["fetched_at"],
        )
        for row in rows
    ]


def recent_high_confidence_items(ticker: str, *, max_age_hours: int = 48, min_confidence: float = 0.6) -> list[NewsItem]:
    """News fresh and credible enough to be promoted to catalysts."""
    items = fetch_news(ticker)
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    out: list[NewsItem] = []
    for item in items:
        if item.confidence < min_confidence:
            continue
        published = item.published_at or item.fetched_at
        try:
            published_dt = datetime.fromisoformat(published.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, AttributeError):
            continue
        if published_dt >= cutoff:
            out.append(item)
    return out
