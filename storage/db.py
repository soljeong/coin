import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, timezone

from config.settings import RETENTION_DAYS_TICKERS, RETENTION_DAYS_OPPORTUNITIES

_SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS tickers (
        id SERIAL PRIMARY KEY,
        exchange TEXT NOT NULL,
        symbol TEXT NOT NULL,
        bid_price DOUBLE PRECISION NOT NULL,
        ask_price DOUBLE PRECISION NOT NULL,
        last_price DOUBLE PRECISION,
        volume_24h DOUBLE PRECISION,
        timestamp TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_tickers_ts ON tickers(timestamp DESC)",
    "CREATE INDEX IF NOT EXISTS idx_tickers_exchange_symbol ON tickers(exchange, symbol)",
    """
    CREATE TABLE IF NOT EXISTS opportunities (
        id SERIAL PRIMARY KEY,
        path TEXT NOT NULL,
        hops INTEGER NOT NULL,
        gross_spread DOUBLE PRECISION NOT NULL,
        net_profit DOUBLE PRECISION NOT NULL,
        total_fees DOUBLE PRECISION NOT NULL,
        risk_level TEXT NOT NULL,
        timestamp TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_opportunities_profit ON opportunities(net_profit DESC)",
]


def init_db(database_url: str) -> psycopg2.extensions.connection:
    """Create tables if not exist, return connection."""
    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    cur = conn.cursor()
    for sql in _SCHEMA_SQL:
        cur.execute(sql)
    conn.commit()
    cur.close()
    return conn


def insert_tickers(conn, tickers: list) -> None:
    """Batch insert ticker data."""
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
    cur = conn.cursor()
    psycopg2.extras.execute_batch(
        cur,
        """
        INSERT INTO tickers (exchange, symbol, bid_price, ask_price, last_price, volume_24h, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )
    conn.commit()
    cur.close()


def cleanup_old_data(conn) -> None:
    """Delete tickers older than RETENTION_DAYS_TICKERS days and
    opportunities older than RETENTION_DAYS_OPPORTUNITIES days."""
    now = datetime.now(timezone.utc)
    ticker_cutoff = (now - timedelta(days=RETENTION_DAYS_TICKERS)).isoformat()
    opp_cutoff = (now - timedelta(days=RETENTION_DAYS_OPPORTUNITIES)).isoformat()

    cur = conn.cursor()
    cur.execute("DELETE FROM tickers WHERE timestamp < %s", (ticker_cutoff,))
    cur.execute("DELETE FROM opportunities WHERE timestamp < %s", (opp_cutoff,))
    conn.commit()
    cur.close()


def insert_opportunities(conn, opportunities: list) -> None:
    """Batch insert arbitrage opportunities."""
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
    cur = conn.cursor()
    psycopg2.extras.execute_batch(
        cur,
        """
        INSERT INTO opportunities (path, hops, gross_spread, net_profit, total_fees, risk_level, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )
    conn.commit()
    cur.close()


def get_latest_opportunities(conn, limit: int = 20) -> list:
    """Return most recent opportunities sorted by net_profit descending."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT * FROM opportunities
        WHERE timestamp >= NOW() - INTERVAL '1 hour'
        ORDER BY net_profit DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall()
    cur.close()
    return [dict(row) for row in rows]


def get_opportunity_history(conn, hours: int = 24) -> list:
    """Return opportunity history for the last N hours."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT * FROM opportunities
        WHERE timestamp >= NOW() - make_interval(hours := %s)
        ORDER BY timestamp DESC
        """,
        (hours,),
    )
    rows = cur.fetchall()
    cur.close()
    return [dict(row) for row in rows]


def get_latest_tickers(conn) -> list:
    """Return the most recent ticker for each (exchange, symbol) pair."""
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT DISTINCT ON (exchange, symbol) *
        FROM tickers
        ORDER BY exchange, symbol, timestamp DESC
        """
    )
    rows = cur.fetchall()
    cur.close()
    return [dict(row) for row in rows]


def get_db_size(conn) -> int:
    """Return database size in bytes."""
    cur = conn.cursor()
    cur.execute("SELECT pg_database_size(current_database())")
    size = cur.fetchone()[0]
    cur.close()
    return size
