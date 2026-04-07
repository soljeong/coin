import sqlite3
import os
from datetime import datetime, timedelta, timezone

from config.settings import RETENTION_DAYS_TICKERS, RETENTION_DAYS_OPPORTUNITIES

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    symbol TEXT NOT NULL,
    bid_price REAL NOT NULL,
    ask_price REAL NOT NULL,
    last_price REAL,
    volume_24h REAL,
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    hops INTEGER NOT NULL,
    gross_spread REAL NOT NULL,
    net_profit REAL NOT NULL,
    total_fees REAL NOT NULL,
    risk_level TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tickers_ts ON tickers(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_tickers_exchange_symbol ON tickers(exchange, symbol);
CREATE INDEX IF NOT EXISTS idx_opportunities_profit ON opportunities(net_profit DESC);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    """Create tables if not exist, return connection.
    Creates the data/ directory if db_path is not :memory:."""
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    return conn


def insert_tickers(conn: sqlite3.Connection, tickers: list) -> None:
    """Batch insert ticker data.

    Each dict must have: exchange, symbol, bid_price, ask_price, volume_24h, timestamp.
    """
    rows = [
        (
            t["exchange"],
            t["symbol"],
            t["bid_price"],
            t["ask_price"],
            t.get("last_price"),
            t.get("volume_24h"),
            t["timestamp"].isoformat() if isinstance(t["timestamp"], datetime) else t["timestamp"],
        )
        for t in tickers
    ]
    conn.executemany(
        """
        INSERT INTO tickers (exchange, symbol, bid_price, ask_price, last_price, volume_24h, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def cleanup_old_data(conn: sqlite3.Connection) -> None:
    """Delete tickers older than RETENTION_DAYS_TICKERS days and
    opportunities older than RETENTION_DAYS_OPPORTUNITIES days."""
    now = datetime.now(timezone.utc)
    ticker_cutoff = (now - timedelta(days=RETENTION_DAYS_TICKERS)).isoformat()
    opp_cutoff = (now - timedelta(days=RETENTION_DAYS_OPPORTUNITIES)).isoformat()

    conn.execute("DELETE FROM tickers WHERE timestamp < ?", (ticker_cutoff,))
    conn.execute("DELETE FROM opportunities WHERE timestamp < ?", (opp_cutoff,))
    conn.commit()


def insert_opportunities(conn: sqlite3.Connection, opportunities: list) -> None:
    """Batch insert arbitrage opportunities.

    Each dict must have: path, hops, gross_spread, net_profit, total_fees, risk_level, timestamp.
    """
    rows = [
        (
            o["path"],
            o["hops"],
            o["gross_spread"],
            o["net_profit"],
            o["total_fees"],
            o["risk_level"],
            o["timestamp"].isoformat() if isinstance(o["timestamp"], datetime) else o["timestamp"],
        )
        for o in opportunities
    ]
    conn.executemany(
        """
        INSERT INTO opportunities (path, hops, gross_spread, net_profit, total_fees, risk_level, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()


def get_latest_opportunities(conn: sqlite3.Connection, limit: int = 20) -> list:
    """Return most recent opportunities sorted by net_profit descending."""
    cursor = conn.execute(
        """
        SELECT * FROM opportunities
        WHERE timestamp >= datetime('now', '-1 hour')
        ORDER BY net_profit DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_opportunity_history(conn: sqlite3.Connection, hours: int = 24) -> list:
    """Return opportunity history for the last N hours."""
    cursor = conn.execute(
        """
        SELECT * FROM opportunities
        WHERE timestamp >= datetime('now', ? || ' hours')
        ORDER BY timestamp DESC
        """,
        (f"-{hours}",),
    )
    return [dict(row) for row in cursor.fetchall()]


def get_latest_tickers(conn: sqlite3.Connection) -> list:
    """Return the most recent ticker for each (exchange, symbol) pair."""
    cursor = conn.execute(
        """
        SELECT t.*
        FROM tickers t
        INNER JOIN (
            SELECT exchange, symbol, MAX(timestamp) AS max_ts
            FROM tickers
            GROUP BY exchange, symbol
        ) latest
        ON t.exchange = latest.exchange
           AND t.symbol = latest.symbol
           AND t.timestamp = latest.max_ts
        ORDER BY t.exchange, t.symbol
        """
    )
    return [dict(row) for row in cursor.fetchall()]
