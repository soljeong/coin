"""Tests for storage/db.py using PostgreSQL.

Requires a running PostgreSQL instance. Set TEST_DATABASE_URL env var
or defaults to postgresql://arb:arb@localhost:5432/arbitrage_test.
"""
import os
import pytest
from datetime import datetime, timedelta, timezone

from storage.db import init_db, insert_tickers, cleanup_old_data, get_latest_tickers


TEST_DATABASE_URL = os.environ.get(
    'TEST_DATABASE_URL',
    'postgresql://arb:arb@localhost:5432/arbitrage_test',
)


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
    c = init_db(TEST_DATABASE_URL)
    yield c
    # Clean up tables after each test
    cur = c.cursor()
    cur.execute("DELETE FROM tickers")
    cur.execute("DELETE FROM opportunities")
    c.commit()
    cur.close()
    c.close()


# --- init_db ---

def test_init_db_creates_tickers_table(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT tablename FROM pg_tables WHERE tablename = 'tickers'"
    )
    result = cur.fetchone()
    cur.close()
    assert result is not None


def test_init_db_creates_opportunities_table(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT tablename FROM pg_tables WHERE tablename = 'opportunities'"
    )
    result = cur.fetchone()
    cur.close()
    assert result is not None


def test_init_db_creates_indexes(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT indexname FROM pg_indexes WHERE tablename IN ('tickers', 'opportunities')"
    )
    indexes = {row[0] for row in cur.fetchall()}
    cur.close()
    assert "idx_tickers_ts" in indexes
    assert "idx_tickers_exchange_symbol" in indexes
    assert "idx_opportunities_profit" in indexes


def test_init_db_idempotent():
    """Calling init_db twice should not raise."""
    c = init_db(TEST_DATABASE_URL)
    c.close()
    c2 = init_db(TEST_DATABASE_URL)
    c2.close()


# --- insert_tickers ---

def test_insert_tickers_stores_data(conn):
    now = datetime.now(timezone.utc)
    tickers = [
        make_ticker("upbit", "BTC", 135_000_000.0, 135_100_000.0, now),
        make_ticker("binance", "BTC", 92_000.0, 92_050.0, now, volume=1234.5),
    ]
    insert_tickers(conn, tickers)

    cur = conn.cursor()
    cur.execute("SELECT * FROM tickers")
    rows = cur.fetchall()
    cur.close()
    assert len(rows) == 2


def test_insert_tickers_field_values(conn):
    now = datetime.now(timezone.utc)
    ticker = make_ticker("upbit", "ETH", 5_000_000.0, 5_010_000.0, now, volume=999.9)
    insert_tickers(conn, [ticker])

    import psycopg2.extras
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tickers WHERE symbol='ETH'")
    row = dict(cur.fetchone())
    cur.close()
    assert row["exchange"] == "upbit"
    assert row["symbol"] == "ETH"
    assert row["bid_price"] == 5_000_000.0
    assert row["ask_price"] == 5_010_000.0
    assert row["volume_24h"] == 999.9


def test_insert_tickers_null_volume(conn):
    now = datetime.now(timezone.utc)
    ticker = make_ticker("upbit", "XRP", 1000.0, 1001.0, now, volume=None)
    insert_tickers(conn, [ticker])

    import psycopg2.extras
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM tickers WHERE symbol='XRP'")
    row = dict(cur.fetchone())
    cur.close()
    assert row["volume_24h"] is None


def test_insert_tickers_accepts_string_timestamp(conn):
    ts_str = "2026-04-06T12:00:00"
    ticker = make_ticker("binance", "SOL", 200.0, 200.5, ts_str)
    insert_tickers(conn, [ticker])

    cur = conn.cursor()
    cur.execute("SELECT * FROM tickers WHERE symbol='SOL'")
    row = cur.fetchone()
    cur.close()
    assert row is not None


# --- cleanup_old_data ---

def test_cleanup_removes_old_tickers(conn):
    now = datetime.now(timezone.utc)
    old_ts = now - timedelta(days=8)
    recent_ts = now - timedelta(days=1)

    insert_tickers(conn, [
        make_ticker("upbit", "BTC", 1.0, 1.1, old_ts),
        make_ticker("upbit", "ETH", 2.0, 2.1, recent_ts),
    ])

    cleanup_old_data(conn)

    cur = conn.cursor()
    cur.execute("SELECT symbol FROM tickers")
    symbols = [r[0] for r in cur.fetchall()]
    cur.close()
    assert "BTC" not in symbols
    assert "ETH" in symbols


def test_cleanup_keeps_recent_tickers(conn):
    now = datetime.now(timezone.utc)
    insert_tickers(conn, [make_ticker("binance", "ADA", 0.5, 0.51, now)])
    cleanup_old_data(conn)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tickers")
    count = cur.fetchone()[0]
    cur.close()
    assert count == 1


def test_cleanup_removes_old_opportunities(conn):
    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=31)).isoformat()
    recent_ts = now.isoformat()

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO opportunities (path, hops, gross_spread, net_profit, total_fees, risk_level, timestamp) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        ('[\"binance:BTC\",\"upbit:BTC\"]', 2, 1.5, 0.8, 0.7, "LOW", old_ts),
    )
    cur.execute(
        "INSERT INTO opportunities (path, hops, gross_spread, net_profit, total_fees, risk_level, timestamp) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        ('[\"binance:ETH\",\"upbit:ETH\"]', 2, 2.0, 1.2, 0.8, "MED", recent_ts),
    )
    conn.commit()
    cur.close()

    cleanup_old_data(conn)

    cur = conn.cursor()
    cur.execute("SELECT path FROM opportunities")
    paths = [r[0] for r in cur.fetchall()]
    cur.close()
    assert '[\"binance:BTC\",\"upbit:BTC\"]' not in paths
    assert '[\"binance:ETH\",\"upbit:ETH\"]' in paths


# --- get_latest_tickers ---

def test_get_latest_tickers_returns_most_recent(conn):
    now = datetime.now(timezone.utc)
    older = now - timedelta(seconds=10)

    insert_tickers(conn, [
        make_ticker("upbit", "BTC", 100.0, 101.0, older),
        make_ticker("upbit", "BTC", 200.0, 201.0, now),
    ])

    result = get_latest_tickers(conn)
    assert len(result) == 1
    assert result[0]["bid_price"] == 200.0


def test_get_latest_tickers_one_per_pair(conn):
    now = datetime.now(timezone.utc)
    older = now - timedelta(seconds=5)

    insert_tickers(conn, [
        make_ticker("upbit", "BTC", 100.0, 101.0, older),
        make_ticker("upbit", "BTC", 105.0, 106.0, now),
        make_ticker("binance", "BTC", 90.0, 90.5, older),
        make_ticker("binance", "BTC", 91.0, 91.5, now),
        make_ticker("upbit", "ETH", 3000.0, 3001.0, now),
    ])

    result = get_latest_tickers(conn)
    assert len(result) == 3


def test_get_latest_tickers_correct_values(conn):
    now = datetime.now(timezone.utc)
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
