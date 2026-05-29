"""Live CEDEAR ratio grid.

CEDEAR ratios (CEDEARs per 1 underlying share) are set by the issuer and
change over time (e.g. after a stock split BYMA/the issuer re-strikes the
ratio). A hardcoded table silently goes stale and re-introduces the exact
valuation bug we fixed once already (SPY's ratio changed recently).

This module fetches the ratio grid LIVE from the **issuer's published
"Programa CEDEAR" table** (Banco Comafi is the local CEDEAR program issuer
and publishes the authoritative ratio grid on its public site). We parse the
HTML table with the stdlib ``html.parser`` — no extra dependency, no PDF/xlsx
library.

Source: https://www.comafi.com.ar/custodiaglobal/2483-Programas-Cedears.note.aspx
The table has, among others, the columns:
  - "Ticker en mercado de origen"        -> the underlying US ticker
  - "Ratio Cedear / valor sub-yacente"   -> the ratio, formatted like "20:1"

Why Comafi and not BYMA open data: BYMA's free ``/cedears`` endpoint only
serves quote/price rows (no ratio field), and the reference-data endpoints
that would carry the ratio require authentication. Comafi's HTML table is the
authoritative, key-free, publicly reachable source for the ratio itself.

Design notes:
  - In-process TTL cache (~24h): ratios never change intra-day, so we fetch at
    most once a day per process. We reuse :class:`market_bot.utils.TTLCache`,
    matching the pattern in ``benchmarks.py``.
  - Soft-fail: any network/parse error returns ``{}`` and logs a warning. This
    function NEVER raises — callers degrade to the canonical static fallback.
"""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser

import requests

from market_bot.utils import TTLCache

logger = logging.getLogger("market_bot.reference.cedear_ratios")

# Issuer-published "Programa CEDEAR" grid (authoritative ratio source).
COMAFI_CEDEAR_URL = (
    "https://www.comafi.com.ar/custodiaglobal/2483-Programas-Cedears.note.aspx"
)

# Ratios are struck by the issuer and only change on corporate actions, never
# intra-day. One fetch per day per process is plenty.
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours
_CACHE_KEY = "comafi_cedear_ratios"

_RATIO_CACHE: TTLCache[dict[str, float]] = TTLCache(ttl_seconds=CACHE_TTL_SECONDS)

# Column header fragments we look for (case/accents-insensitive substring match).
_TICKER_HEADER_HINT = "ticker en mercado de origen"
_RATIO_HEADER_HINT = "ratio"

_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")


def _normalize(symbol: str) -> str:
    """Normalise a ticker for table-key use (uppercase, trimmed)."""
    return str(symbol or "").strip().upper()


def _parse_ratio(raw_value: str) -> float | None:
    """Parse a Comafi ratio cell.

    The grid uses ``"<cedears>:<underlying>"`` notation, e.g. ``"20:1"``
    (20 CEDEARs per 1 underlying) or ``"1:3"`` (1 CEDEAR per 3 underlying,
    i.e. ratio 0.333...). A bare number is also accepted.
    """
    value = str(raw_value or "").strip()
    if not value:
        return None
    value = value.replace(",", ".")
    left, separator, right = value.partition(":")
    try:
        if separator:
            denominator = float(right or 1)
            numerator = float(left)
            if denominator <= 0 or numerator <= 0:
                return None
            return round(numerator / denominator, 6)
        parsed = float(value)
        return parsed if parsed > 0 else None
    except ValueError:
        return None


class _CedearTableParser(HTMLParser):
    """Extract ``{ticker: ratio}`` from the Comafi HTML "Programa CEDEAR" table.

    The parser is column-position-agnostic: it locates the header row, finds the
    indices of the ticker and ratio columns by their header text, then reads the
    matching cells from every data row. This survives column re-ordering on the
    issuer's side.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_cell = False
        self._cell_parts: list[str] = []
        self._row_cells: list[str] = []
        self._header_seen = False
        self._ticker_idx: int | None = None
        self._ratio_idx: int | None = None
        self.ratios: dict[str, float] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("td", "th"):
            self._in_cell = True
            self._cell_parts = []
        elif tag == "tr":
            self._row_cells = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th"):
            self._in_cell = False
            self._row_cells.append(" ".join("".join(self._cell_parts).split()))
        elif tag == "tr":
            self._flush_row()

    def _flush_row(self) -> None:
        cells = self._row_cells
        self._row_cells = []
        if not cells:
            return

        if not self._header_seen:
            lowered = [c.lower() for c in cells]
            ticker_idx = next(
                (i for i, c in enumerate(lowered) if _TICKER_HEADER_HINT in c),
                None,
            )
            ratio_idx = next(
                (i for i, c in enumerate(lowered) if _RATIO_HEADER_HINT in c),
                None,
            )
            if ticker_idx is not None and ratio_idx is not None:
                self._ticker_idx = ticker_idx
                self._ratio_idx = ratio_idx
                self._header_seen = True
            return

        if self._ticker_idx is None or self._ratio_idx is None:
            return
        if len(cells) <= max(self._ticker_idx, self._ratio_idx):
            return

        ticker = _normalize(cells[self._ticker_idx])
        ratio = _parse_ratio(cells[self._ratio_idx])
        if not ticker or not _TICKER_RE.match(ticker) or ratio is None:
            return
        # First occurrence wins; the grid lists one row per program.
        self.ratios.setdefault(ticker, ratio)


def _parse_cedear_table(html: str) -> dict[str, float]:
    parser = _CedearTableParser()
    parser.feed(html)
    return parser.ratios


def fetch_cedear_ratios(*, force_refresh: bool = False) -> dict[str, float]:
    """Fetch the live issuer-published CEDEAR ratio grid.

    Returns a ``{normalized_ticker: ratio}`` dict where ``ratio`` is the number
    of CEDEARs per 1 underlying share. Result is cached in-process for ~24h.

    Soft-fail contract: on ANY network/parse error this returns ``{}`` and logs
    a warning — it never raises. Callers must treat an empty dict as "no live
    data" and fall back to their static table.
    """
    if not force_refresh:
        cached = _RATIO_CACHE.get(_CACHE_KEY)
        if cached is not None:
            return cached

    try:
        response = requests.get(
            COMAFI_CEDEAR_URL,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (market_bot reference_data)"},
        )
        response.raise_for_status()
        ratios = _parse_cedear_table(response.text)
    except Exception as exc:  # noqa: BLE001 - soft-fail by contract
        logger.warning("Live CEDEAR ratio fetch failed: %s", exc)
        return {}

    if not ratios:
        # Reachable page but the table layout changed / nothing parsed. Don't
        # cache the empty result so the next call retries.
        logger.warning(
            "Live CEDEAR ratio fetch returned no rows (table layout may have "
            "changed at %s)",
            COMAFI_CEDEAR_URL,
        )
        return {}

    return _RATIO_CACHE.set(_CACHE_KEY, ratios)


def live_cedear_ratio(symbol: str) -> float | None:
    """Return the live ratio for ``symbol`` or ``None`` if unavailable.

    Reads from the cached :func:`fetch_cedear_ratios` grid. Never raises; if
    the live grid is empty (soft-fail) this returns ``None`` and the caller
    should fall back to its canonical table.
    """
    normalized = _normalize(symbol)
    if not normalized:
        return None
    return fetch_cedear_ratios().get(normalized)


def clear_cedear_ratio_cache() -> None:
    """Drop the cached live grid (mainly for tests / forced refresh)."""
    # TTLCache has no public delete; reach into its store for a true eviction
    # so the next fetch re-hits the network instead of serving a stale grid.
    _RATIO_CACHE._store.pop(_CACHE_KEY, None)
