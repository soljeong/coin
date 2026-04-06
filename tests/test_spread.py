"""Tests for analysis/spread.py - bridge coin spread calculator."""

import pytest
from unittest.mock import patch

from analysis.spread import _build_price_map, calc_implied_rate, calc_spreads


def make_ticker(exchange, symbol, bid, ask, last=None, volume=None):
    return {
        "exchange": exchange,
        "symbol": symbol,
        "bid_price": bid,
        "ask_price": ask,
        "last_price": last,
        "volume_24h": volume,
    }


# --- _build_price_map ---

def test_build_price_map_basic():
    tickers = [
        make_ticker("upbit", "BTC", 95000000, 95100000),
        make_ticker("binance", "BTC", 69000, 69100),
    ]
    pm = _build_price_map(tickers)
    assert ("upbit", "BTC") in pm
    assert ("binance", "BTC") in pm
    assert pm[("upbit", "BTC")]["bid_price"] == 95000000


def test_build_price_map_empty():
    assert _build_price_map([]) == {}


# --- calc_implied_rate ---

@patch("analysis.spread.BRIDGE_COINS", ["XRP"])
@patch("analysis.spread.WITHDRAWAL_FEES", {"XRP": 1.0})
def test_implied_rate_single_bridge():
    """XRP on Upbit at 900 KRW bid, Binance at 0.6 USDT ask → rate = 1500."""
    pm = {
        ("upbit", "XRP"): make_ticker("upbit", "XRP", 900, 910),
        ("binance", "XRP"): make_ticker("binance", "XRP", 0.59, 0.6),
    }
    rate = calc_implied_rate(pm)
    assert rate == pytest.approx(900 / 0.6, rel=1e-6)


@patch("analysis.spread.BRIDGE_COINS", ["XRP", "XLM"])
@patch("analysis.spread.WITHDRAWAL_FEES", {"XRP": 1.0, "XLM": 0.1})
def test_implied_rate_multiple_bridges():
    """Average of XRP and XLM implied rates."""
    pm = {
        ("upbit", "XRP"): make_ticker("upbit", "XRP", 900, 910),
        ("binance", "XRP"): make_ticker("binance", "XRP", 0.59, 0.6),
        ("upbit", "XLM"): make_ticker("upbit", "XLM", 450, 455),
        ("binance", "XLM"): make_ticker("binance", "XLM", 0.29, 0.3),
    }
    rate = calc_implied_rate(pm)
    xrp_rate = 900 / 0.6
    xlm_rate = 450 / 0.3
    assert rate == pytest.approx((xrp_rate + xlm_rate) / 2, rel=1e-6)


@patch("analysis.spread.BRIDGE_COINS", ["XRP"])
@patch("analysis.spread.WITHDRAWAL_FEES", {"XRP": 1.0})
def test_implied_rate_missing_exchange():
    """Only Upbit data, no Binance → None."""
    pm = {
        ("upbit", "XRP"): make_ticker("upbit", "XRP", 900, 910),
    }
    rate = calc_implied_rate(pm)
    assert rate is None


@patch("analysis.spread.BRIDGE_COINS", ["XRP"])
@patch("analysis.spread.WITHDRAWAL_FEES", {"XRP": 1.0})
def test_implied_rate_zero_ask():
    """Binance ask = 0 should be skipped."""
    pm = {
        ("upbit", "XRP"): make_ticker("upbit", "XRP", 900, 910),
        ("binance", "XRP"): make_ticker("binance", "XRP", 0, 0),
    }
    rate = calc_implied_rate(pm)
    assert rate is None


# --- calc_spreads ---

@patch("analysis.spread.BRIDGE_COINS", ["XRP"])
@patch("analysis.spread.WITHDRAWAL_FEES", {"XRP": 1.0})
@patch("analysis.spread.UPBIT_FEE", 0.0005)
@patch("analysis.spread.BINANCE_FEE", 0.001)
def test_calc_spreads_basic():
    """BTC with known prices and implied rate from XRP."""
    # XRP: implied rate = 900 / 0.6 = 1500 KRW/USDT
    # BTC Upbit bid: 105,000,000 KRW → 70,000 USDT at implied rate
    # BTC Binance ask: 69,000 USDT
    # Gross premium: (70000/69000 - 1) * 100 = ~1.449%
    tickers = [
        make_ticker("upbit", "XRP", 900, 910),
        make_ticker("binance", "XRP", 0.59, 0.6),
        make_ticker("upbit", "BTC", 105000000, 105100000),
        make_ticker("binance", "BTC", 68900, 69000),
    ]
    results = calc_spreads(tickers)
    assert len(results) >= 1

    btc = next(r for r in results if r["symbol"] == "BTC")
    # Gross: (105000000/1500) / 69000 - 1 = 70000/69000 - 1 ≈ 1.449%
    assert btc["gross_premium_pct"] == pytest.approx(1.4493, rel=0.01)
    # Fee: (0.001 + 0.0005) * 100 = 0.15%
    assert btc["total_fee_pct"] == pytest.approx(0.15, rel=1e-6)
    # Net: ~1.449 - 0.15 = ~1.299
    assert btc["net_spread_pct"] == pytest.approx(1.2993, rel=0.01)


@patch("analysis.spread.BRIDGE_COINS", ["XRP"])
@patch("analysis.spread.WITHDRAWAL_FEES", {"XRP": 1.0})
def test_calc_spreads_sorted_descending():
    """Results sorted by net_spread_pct descending."""
    tickers = [
        make_ticker("upbit", "XRP", 900, 910),
        make_ticker("binance", "XRP", 0.59, 0.6),
        # BTC: high premium
        make_ticker("upbit", "BTC", 110000000, 110100000),
        make_ticker("binance", "BTC", 68900, 69000),
        # ETH: lower premium
        make_ticker("upbit", "ETH", 5100000, 5110000),
        make_ticker("binance", "ETH", 3490, 3500),
    ]
    results = calc_spreads(tickers)
    assert len(results) >= 2
    # Check descending order
    for i in range(len(results) - 1):
        assert results[i]["net_spread_pct"] >= results[i + 1]["net_spread_pct"]


@patch("analysis.spread.BRIDGE_COINS", ["XRP"])
@patch("analysis.spread.WITHDRAWAL_FEES", {"XRP": 1.0})
def test_calc_spreads_no_bridge_data():
    """No bridge coin data → empty results."""
    tickers = [
        make_ticker("upbit", "BTC", 105000000, 105100000),
        make_ticker("binance", "BTC", 68900, 69000),
    ]
    results = calc_spreads(tickers)
    assert results == []


@patch("analysis.spread.BRIDGE_COINS", ["XRP"])
@patch("analysis.spread.WITHDRAWAL_FEES", {"XRP": 1.0})
def test_calc_spreads_with_precomputed_rate():
    """Pass implied_rate directly, skip bridge coin calculation."""
    tickers = [
        make_ticker("upbit", "BTC", 105000000, 105100000),
        make_ticker("binance", "BTC", 68900, 69000),
    ]
    results = calc_spreads(tickers, implied_rate=1500.0)
    assert len(results) == 1
    assert results[0]["symbol"] == "BTC"
    assert results[0]["implied_rate"] == 1500.0


@patch("analysis.spread.BRIDGE_COINS", ["XRP"])
@patch("analysis.spread.WITHDRAWAL_FEES", {"XRP": 1.0})
def test_calc_spreads_single_exchange_only():
    """Coin on only one exchange is excluded."""
    tickers = [
        make_ticker("upbit", "XRP", 900, 910),
        make_ticker("binance", "XRP", 0.59, 0.6),
        make_ticker("upbit", "SOL", 250000, 251000),
        # No Binance SOL
    ]
    results = calc_spreads(tickers)
    symbols = [r["symbol"] for r in results]
    assert "SOL" not in symbols


def test_calc_spreads_empty_tickers():
    """Empty ticker list → empty results."""
    results = calc_spreads([])
    assert results == []


@patch("analysis.spread.BRIDGE_COINS", ["XRP"])
@patch("analysis.spread.WITHDRAWAL_FEES", {"XRP": 1.0})
def test_calc_spreads_negative_premium():
    """When Upbit is cheaper than Binance, premium is negative."""
    # Implied rate = 900/0.6 = 1500
    # BTC: Upbit 100M KRW = 66666 USDT, Binance ask 69000
    # Premium = (66666/69000 - 1) = negative
    tickers = [
        make_ticker("upbit", "XRP", 900, 910),
        make_ticker("binance", "XRP", 0.59, 0.6),
        make_ticker("upbit", "BTC", 100000000, 100100000),
        make_ticker("binance", "BTC", 68900, 69000),
    ]
    results = calc_spreads(tickers)
    btc = next(r for r in results if r["symbol"] == "BTC")
    assert btc["net_spread_pct"] < 0
