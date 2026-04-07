"""Tests for analysis/graph.py — graph engine and Bellman-Ford cycle detection."""

import math
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from analysis.graph import (
    build_graph,
    find_arbitrage_cycles,
    detect_opportunities,
    _assess_risk,
    _normalize_cycle,
)


def make_ticker(exchange, symbol, bid, ask, last=None, volume=None):
    return {
        "exchange": exchange,
        "symbol": symbol,
        "bid_price": bid,
        "ask_price": ask,
        "last_price": last,
        "volume_24h": volume,
    }


# --- build_graph ---

@patch("analysis.graph.WITHDRAWAL_FEES", {"XRP": 1.0, "BTC": 0.0005})
def test_build_graph_creates_nodes():
    tickers = [
        make_ticker("upbit", "BTC", 95000000, 95100000),
        make_ticker("upbit", "XRP", 900, 910),
        make_ticker("binance", "BTC", 69000, 69100),
        make_ticker("binance", "XRP", 0.59, 0.6),
    ]
    nodes, edges = build_graph(tickers, implied_rate=1400.0)
    assert "upbit:BTC" in nodes
    assert "upbit:XRP" in nodes
    assert "binance:BTC" in nodes
    assert "binance:XRP" in nodes
    assert len(nodes) == 4


@patch("analysis.graph.WITHDRAWAL_FEES", {"XRP": 1.0})
def test_build_graph_has_trade_edges():
    """Intra-exchange trade edges should exist."""
    tickers = [
        make_ticker("upbit", "BTC", 95000000, 95100000),
        make_ticker("upbit", "XRP", 900, 910),
    ]
    nodes, edges = build_graph(tickers, implied_rate=1400.0)
    trade_edges = [e for e in edges if e[3]["type"] == "trade"]
    # upbit:BTC->upbit:XRP and upbit:XRP->upbit:BTC
    assert len(trade_edges) == 2


@patch("analysis.graph.WITHDRAWAL_FEES", {"BTC": 0.0005})
def test_build_graph_has_transfer_edges():
    """Cross-exchange transfer edges should exist for coins on both exchanges."""
    tickers = [
        make_ticker("upbit", "BTC", 95000000, 95100000),
        make_ticker("binance", "BTC", 69000, 69100),
    ]
    nodes, edges = build_graph(tickers, implied_rate=1400.0)
    transfer_edges = [e for e in edges if e[3]["type"] == "transfer"]
    # Both directions: upbit:BTC->binance:BTC and binance:BTC->upbit:BTC
    assert len(transfer_edges) == 2


@patch("analysis.graph.WITHDRAWAL_FEES", {})
def test_build_graph_empty_tickers():
    nodes, edges = build_graph([], implied_rate=1400.0)
    assert nodes == []
    assert edges == []


# --- find_arbitrage_cycles ---

def test_find_cycles_no_negative_cycle():
    """When all weights are positive, no opportunities should be found."""
    nodes = ["A", "B", "C"]
    # All edges have positive weights (no profit)
    edges = [
        ("A", "B", 0.1, {"type": "trade", "fee": 0.001, "rate": 0.9}),
        ("B", "C", 0.1, {"type": "trade", "fee": 0.001, "rate": 0.9}),
        ("C", "A", 0.1, {"type": "trade", "fee": 0.001, "rate": 0.9}),
    ]
    result = find_arbitrage_cycles(nodes, edges)
    assert result == []


@patch("analysis.graph.MIN_NET_PROFIT_PCT", 0.0)
def test_find_cycles_with_negative_cycle():
    """A->B->C->A with negative total weight should be detected."""
    nodes = ["A", "B", "C"]
    # Create a cycle where the product of rates > 1
    # rate = 1.05 each => product = 1.05^3 = 1.157 => profit = 15.7%
    edges = [
        ("A", "B", -math.log(1.05), {"type": "trade", "fee": 0.001, "rate": 1.05}),
        ("B", "C", -math.log(1.05), {"type": "trade", "fee": 0.001, "rate": 1.05}),
        ("C", "A", -math.log(1.05), {"type": "trade", "fee": 0.001, "rate": 1.05}),
    ]
    result = find_arbitrage_cycles(nodes, edges)
    assert len(result) >= 1
    assert result[0]["net_profit"] > 0


def test_find_cycles_empty_graph():
    result = find_arbitrage_cycles([], [])
    assert result == []


@patch("analysis.graph.MIN_NET_PROFIT_PCT", 0.0)
def test_find_cycles_respects_max_hops():
    """Cycles longer than max_hops should not be detected."""
    nodes = ["A", "B", "C", "D", "E", "F"]
    edges = [
        ("A", "B", -math.log(1.02), {"type": "trade", "fee": 0.001, "rate": 1.02}),
        ("B", "C", -math.log(1.02), {"type": "trade", "fee": 0.001, "rate": 1.02}),
        ("C", "D", -math.log(1.02), {"type": "trade", "fee": 0.001, "rate": 1.02}),
        ("D", "E", -math.log(1.02), {"type": "trade", "fee": 0.001, "rate": 1.02}),
        ("E", "F", -math.log(1.02), {"type": "trade", "fee": 0.001, "rate": 1.02}),
        ("F", "A", -math.log(1.02), {"type": "trade", "fee": 0.001, "rate": 1.02}),
    ]
    # With max_hops=3, this 6-hop cycle should NOT be found
    result = find_arbitrage_cycles(nodes, edges, max_hops=3)
    long_cycles = [r for r in result if r["hops"] > 3]
    assert len(long_cycles) == 0


# --- _assess_risk ---

def test_risk_low():
    assert _assess_risk(1.5, 2) == "LOW"


def test_risk_med_high_profit_many_hops():
    assert _assess_risk(0.6, 4) == "MED"


def test_risk_high():
    assert _assess_risk(0.3, 5) == "HIGH"


# --- _normalize_cycle ---

def test_normalize_cycle():
    assert _normalize_cycle(["C", "A", "B"]) == ["A", "B", "C"]
    assert _normalize_cycle(["B", "C", "A"]) == ["A", "B", "C"]


def test_normalize_cycle_empty():
    assert _normalize_cycle([]) == []


# --- detect_opportunities (integration) ---

@patch("analysis.graph.WITHDRAWAL_FEES", {"XRP": 1.0})
@patch("analysis.graph.MIN_NET_PROFIT_PCT", 0.0)
@patch("analysis.spread.BRIDGE_COINS", ["XRP"])
@patch("analysis.spread.WITHDRAWAL_FEES", {"XRP": 1.0})
def test_detect_opportunities_returns_list():
    """Integration test: detect_opportunities should return a list."""
    tickers = [
        make_ticker("upbit", "XRP", 900, 910),
        make_ticker("binance", "XRP", 0.59, 0.6),
        make_ticker("upbit", "BTC", 105000000, 105100000),
        make_ticker("binance", "BTC", 69000, 69100),
    ]
    result = detect_opportunities(tickers)
    assert isinstance(result, list)
    # Each opportunity should have required fields
    for opp in result:
        assert "path" in opp
        assert "hops" in opp
        assert "net_profit" in opp
        assert "risk_level" in opp
        assert "timestamp" in opp


def test_detect_opportunities_empty():
    assert detect_opportunities([]) == []


@patch("analysis.spread.BRIDGE_COINS", ["NONE"])
@patch("analysis.spread.WITHDRAWAL_FEES", {})
def test_detect_opportunities_no_implied_rate():
    """Without bridge coin data, should return empty."""
    tickers = [
        make_ticker("upbit", "BTC", 105000000, 105100000),
        make_ticker("binance", "BTC", 69000, 69100),
    ]
    result = detect_opportunities(tickers)
    assert result == []
