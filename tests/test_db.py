"""Tests for storage/db.py using in-memory SQLite."""
import pytest
from datetime import datetime, timedelta

from storage.db import init_db, insert_tickers, cleanup_old_data, get_latest_tickers


def make_ticker(exchange, symbol, bid, ask, ts, volume=None):
    return {
        "exchange": exchange,
        "symbol": symbol,
        "bid_price": bid,
        "ask_price": ask,
        "volume_24h": volume,
        "timestamp": ts,
    }


@pytest.fixture
def conn():
    c = init_db(":memory:")
    yield c
    c.close()


# --- init_db ---

def test_init_db_creates_tickers_table(conn):
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tickers'"
    ).fetchone()
    assert result is not None


def test_init_db_creates_opportunities_table(conn):
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='opportunities'"
    ).fetchone()
    assert result is not None


def test_init_db_creates_indexes(conn):
    indexes = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    }
    assert "idx_tickers_ts" in indexes
    assert "idx_tickers_exchange_symbol" in indexes
    assert "idx_opportunities_profit" in indexes


def test_init_db_idempotent():
    """Calling init_db twice should not raise."""
    c = init_db(":memory:")
    c.close()
    # second call on same path (new in-memory DB — just verifying no exception)
    c2 = init_db(":memory:")
    c2.close()


# --- insert_tickers ---

def test_insert_tickers_stores_data(conn):
    now = datetime.utcnow()
    tickers = [
        make_ticker("upbit", "BTC", 135_000_000.0, 135_100_000.0, now),
        make_ticker("binance", "BTC", 92_000.0, 92_050.0, now, volume=1234.5),
    ]
    insert_tickers(conn, tickers)

    rows = conn.execute("SELECT * FROM tickers").fetchall()
    assert len(rows) == 2


def test_insert_tickers_field_values(conn):
    now = datetime.utcnow()
    ticker = make_ticker("upbit", "ETH", 5_000_000.0, 5_010_000.0, now, volume=999.9)
    insert_tickers(conn, [ticker])

    row = dict(conn.execute("SELECT * FROM tickers WHERE symbol='ETH'").fetchone())
    assert row["exchange"] == "upbit"
    assert row["symbol"] == "ETH"
    assert row["bid_price"] == 5_000_000.0
    assert row["ask_price"] == 5_010_000.0
    assert row["volume_24h"] == 999.9


def test_insert_tickers_null_volume(conn):
    now = datetime.utcnow()
    ticker = make_ticker("upbit", "XRP", 1000.0, 1001.0, now, volume=None)
    insert_tickers(conn, [ticker])

    row = dict(conn.execute("SELECT * FROM tickers WHERE symbol='XRP'").fetchone())
    assert row["volume_24h"] is None


def test_insert_tickers_accepts_string_timestamp(conn):
    ts_str = "2026-04-06T12:00:00"
    ticker = make_ticker("binance", "SOL", 200.0, 200.5, ts_str)
    insert_tickers(conn, [ticker])

    row = conn.execute("SELECT * FROM tickers WHERE symbol='SOL'").fetchone()
    assert row is not None


# --- cleanup_old_data ---

def test_cleanup_removes_old_tickers(conn):
    now = datetime.utcnow()
    old_ts = now - timedelta(days=8)   # older than 7-day retention
    recent_ts = now - timedelta(days=1)

    insert_tickers(conn, [
        make_ticker("upbit", "BTC", 1.0, 1.1, old_ts),
        make_ticker("upbit", "ETH", 2.0, 2.1, recent_ts),
    ])

    cleanup_old_data(conn)

    rows = conn.execute("SELECT symbol FROM tickers").fetchall()
    symbols = [r[0] for r in rows]
    assert "BTC" not in symbols
    assert "ETH" in symbols


def test_cleanup_keeps_recent_tickers(conn):
    now = datetime.utcnow()
    insert_tickers(conn, [make_ticker("binance", "ADA", 0.5, 0.51, now)])
    cleanup_old_data(conn)

    count = conn.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]
    assert count == 1


def test_cleanup_removes_old_opportunities(conn):
    now = datetime.utcnow()
    old_ts = (now - timedelta(days=31)).isoformat()
    recent_ts = now.isoformat()

    conn.execute(
        "INSERT INTO opportunities (path, hops, gross_spread, net_profit, total_fees, risk_level, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ('["binance:BTC","upbit:BTC"]', 2, 1.5, 0.8, 0.7, "LOW", old_ts),
    )
    conn.execute(
        "INSERT INTO opportunities (path, hops, gross_spread, net_profit, total_fees, risk_level, timestamp) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ('["binance:ETH","upbit:ETH"]', 2, 2.0, 1.2, 0.8, "MED", recent_ts),
    )
    conn.commit()

    cleanup_old_data(conn)

    rows = conn.execute("SELECT path FROM opportunities").fetchall()
    paths = [r[0] for r in rows]
    assert '["binance:BTC","upbit:BTC"]' not in paths
    assert '["binance:ETH","upbit:ETH"]' in paths


# --- get_latest_tickers ---

def test_get_latest_tickers_returns_most_recent(conn):
    now = datetime.utcnow()
    older = now - timedelta(seconds=10)

    insert_tickers(conn, [
        make_ticker("upbit", "BTC", 100.0, 101.0, older),
        make_ticker("upbit", "BTC", 200.0, 201.0, now),   # newer — should win
    ])

    result = get_latest_tickers(conn)
    assert len(result) == 1
    assert result[0]["bid_price"] == 200.0


def test_get_latest_tickers_one_per_pair(conn):
    now = datetime.utcnow()
    older = now - timedelta(seconds=5)

    insert_tickers(conn, [
        make_ticker("upbit", "BTC", 100.0, 101.0, older),
        make_ticker("upbit", "BTC", 105.0, 106.0, now),
        make_ticker("binance", "BTC", 90.0, 90.5, older),
        make_ticker("binance", "BTC", 91.0, 91.5, now),
        make_ticker("upbit", "ETH", 3000.0, 3001.0, now),
    ])

    result = get_latest_tickers(conn)
    # 3 unique (exchange, symbol) pairs
    assert len(result) == 3


def test_get_latest_tickers_correct_values(conn):
    now = datetime.utcnow()
    insert_tickers(conn, [
        make_ticker("binance", "XRP", 0.5, 0.51, now - timedelta(seconds=3)),
        make_ticker("binance", "XRP", 0.6, 0.61, now),
    ])

    result = get_latest_tickers(conn)
    assert len(result) == 1
    assert result[0]["bid_price"] == 0.6
    assert result[0]["ask_price"] == 0.61


def test_get_latest_tickers_empty(conn):
    result = get_latest_tickers(conn)
    assert result == []
