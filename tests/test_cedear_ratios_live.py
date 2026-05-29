"""Sprint 13.1 — live CEDEAR ratio source.

Fully offline. We mock the live fetch (``fetch_cedear_ratios`` /
``live_cedear_ratio``) and assert:

  1. When the live grid has the ticker, ``resolve_cedear_reference`` uses it
     with ``ratio_source="byma_live"`` and the exact live value — even when a
     (different) canonical ratio also exists. Live wins.
  2. When the live grid is empty (soft-fail), resolution falls back to the
     canonical static table — preserving prior behaviour.
  3. The module-level soft-fail contract: a network/parse error inside
     ``fetch_cedear_ratios`` returns ``{}`` and never raises.

These tests NEVER touch the network: every external call is monkeypatched.
"""

from __future__ import annotations

import sys

import market_portfolio.cedears as cedears
import market_reference.cedear_ratios as cedear_ratios
from market_portfolio.cedears import resolve_cedear_reference


def _live_module():
    """Return the live ratios module that ``cedears`` will lazily import.

    Other tests (e.g. the ``api_client`` fixture) pop and reimport the
    ``market_reference`` package, so the module object bound at import time can
    go stale. Resolving via ``sys.modules`` guarantees we patch the object the
    production lazy import will actually pick up.
    """
    return sys.modules.get("market_reference.cedear_ratios", cedear_ratios)


def test_live_ratio_wins_over_canonical(monkeypatch):
    # AAPL canonical is 20.0. Live grid says 25.0 — live must win.
    monkeypatch.setattr(cedears, "_live_cedear_ratio", lambda sym: 25.0 if sym == "AAPL" else None)

    ref = resolve_cedear_reference(
        symbol="AAPL",
        underlying_ticker="AAPL",
        user_ratio=None,
        current_ccl=1200.0,
        local_price_ars=21500.0,
        underlying_price_usd=180.0,
    )
    assert ref.ratio_source == "byma_live"
    assert ref.cedear_ratio == 25.0


def test_user_supplied_still_beats_live(monkeypatch):
    monkeypatch.setattr(cedears, "_live_cedear_ratio", lambda sym: 25.0)

    ref = resolve_cedear_reference(
        symbol="AAPL",
        underlying_ticker="AAPL",
        user_ratio=12.0,
        current_ccl=None,
        local_price_ars=None,
        underlying_price_usd=None,
    )
    assert ref.ratio_source == "user_supplied"
    assert ref.cedear_ratio == 12.0


def test_empty_live_grid_falls_back_to_canonical(monkeypatch):
    # Live fetch returns nothing -> live_cedear_ratio is None -> canonical wins.
    live_mod = _live_module()
    monkeypatch.setattr(live_mod, "fetch_cedear_ratios", lambda **_: {})
    live_mod.clear_cedear_ratio_cache()

    ref = resolve_cedear_reference(
        symbol="AAPL",
        underlying_ticker="AAPL",
        user_ratio=None,
        current_ccl=None,
        local_price_ars=None,
        underlying_price_usd=None,
    )
    assert ref.ratio_source == "builtin_canonical"
    assert ref.cedear_ratio == 20.0


def test_live_ratio_resolves_via_live_grid_through_real_lookup(monkeypatch):
    # Exercise the real _live_cedear_ratio path (not the stub) by mocking the
    # underlying grid fetch. Confirms the wiring from grid -> resolution.
    #
    # ``cedears._live_cedear_ratio`` imports ``market_reference.cedear_ratios``
    # lazily, so we patch the module object that *that* import will resolve to
    # via sys.modules (other tests may have reimported the package, leaving the
    # top-level ``cedear_ratios`` reference stale).
    live_mod = _live_module()
    monkeypatch.setattr(
        live_mod, "fetch_cedear_ratios", lambda **_: {"AAPL": 30.0, "MSFT": 30.0}
    )
    live_mod.clear_cedear_ratio_cache()

    ref = resolve_cedear_reference(
        symbol="AAPL",
        underlying_ticker="AAPL",
        user_ratio=None,
        current_ccl=None,
        local_price_ars=None,
        underlying_price_usd=None,
    )
    assert ref.ratio_source == "byma_live"
    assert ref.cedear_ratio == 30.0


def test_fetch_soft_fails_on_network_error(monkeypatch):
    live_mod = _live_module()
    live_mod.clear_cedear_ratio_cache()

    def _boom(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(live_mod.requests, "get", _boom)
    # Must not raise; must return an empty dict.
    assert live_mod.fetch_cedear_ratios(force_refresh=True) == {}
    assert live_mod.live_cedear_ratio("AAPL") is None


def test_parse_ratio_handles_issuer_notation():
    # "20:1" -> 20.0 ; "1:3" -> 0.3333... ; bare number passthrough.
    assert cedear_ratios._parse_ratio("20:1") == 20.0
    assert round(cedear_ratios._parse_ratio("1:3"), 4) == 0.3333
    assert cedear_ratios._parse_ratio("15") == 15.0
    assert cedear_ratios._parse_ratio("") is None
    assert cedear_ratios._parse_ratio("0:1") is None


def test_parse_table_extracts_ticker_and_ratio_columns():
    # Minimal HTML mirroring the Comafi grid header + two data rows.
    html = """
    <table>
      <tr>
        <th>Programa de CEDEAR</th>
        <th>Ticker en mercado de origen</th>
        <th>Ratio Cedear / valor sub-yacente</th>
      </tr>
      <tr><td>Apple</td><td>AAPL</td><td>20:1</td></tr>
      <tr><td>Amazon</td><td>AMZN</td><td>144:1</td></tr>
      <tr><td>Ambev</td><td>ABEV</td><td>1:3</td></tr>
    </table>
    """
    parsed = cedear_ratios._parse_cedear_table(html)
    assert parsed["AAPL"] == 20.0
    assert parsed["AMZN"] == 144.0
    assert round(parsed["ABEV"], 4) == 0.3333
