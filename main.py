"""Entry point: polling loop that collects exchange data, analyzes, and serves dashboard."""

import logging
import os
import threading
import time
from datetime import datetime, timezone

import uvicorn

from config.settings import (
    POLLING_INTERVAL,
    DB_PATH,
    RETRY_DELAY,
    MAX_RETRIES,
    BACKOFF_DELAY,
    DATA_STALE_THRESHOLD,
    CLEANUP_INTERVAL,
    DASHBOARD_HOST,
    DASHBOARD_PORT,
)
from storage.db import init_db, insert_tickers, insert_opportunities, cleanup_old_data
from collectors.exchange import ExchangeCollector
from analysis.spread import calc_spreads
from analysis.graph import detect_opportunities

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


def run_loop():
    """Main polling loop."""
    logger.info("Initializing database at %s", DB_PATH)
    conn = init_db(DB_PATH)

    collector = ExchangeCollector()

    # Initial cleanup
    logger.info("Running initial data cleanup")
    cleanup_old_data(conn)

    last_success_time = time.monotonic()
    last_cleanup_time = time.monotonic()
    consecutive_failures = 0

    try:
        while True:
            try:
                tickers = collector.collect_all()

                if tickers:
                    insert_tickers(conn, tickers)
                    last_success_time = time.monotonic()
                    consecutive_failures = 0

                    # Log collection stats
                    exchanges = {}
                    for t in tickers:
                        ex = t["exchange"]
                        exchanges[ex] = exchanges.get(ex, 0) + 1
                    stats = ", ".join(f"{ex}={cnt}" for ex, cnt in sorted(exchanges.items()))
                    logger.info("Collected %d tickers (%s)", len(tickers), stats)

                    # Calculate spreads
                    spreads = calc_spreads(tickers)
                    if spreads:
                        top = spreads[0]
                        logger.info(
                            "Top spread: %s gross=%.2f%% net=%.2f%% (rate=%.0f KRW/USDT)",
                            top["symbol"], top["gross_premium_pct"],
                            top["net_spread_pct"], top["implied_rate"],
                        )
                        for s in spreads[:5]:
                            logger.info(
                                "  %s: gross=%.2f%% net=%.2f%%",
                                s["symbol"], s["gross_premium_pct"], s["net_spread_pct"],
                            )

                    # Detect arbitrage opportunities via graph engine
                    opportunities = detect_opportunities(tickers)
                    if opportunities:
                        insert_opportunities(conn, opportunities)
                        logger.info(
                            "Stored %d opportunities (best: %.2f%%)",
                            len(opportunities),
                            opportunities[0]["net_profit"] if isinstance(opportunities[0]["net_profit"], (int, float)) else 0,
                        )
                else:
                    logger.warning("No tickers collected this cycle")

                # Check data staleness
                elapsed = time.monotonic() - last_success_time
                if elapsed > DATA_STALE_THRESHOLD:
                    logger.warning(
                        "DATA STALE: no successful collection for %.1f seconds", elapsed
                    )

                # Periodic cleanup
                if time.monotonic() - last_cleanup_time >= CLEANUP_INTERVAL:
                    logger.info("Running periodic data cleanup")
                    cleanup_old_data(conn)
                    last_cleanup_time = time.monotonic()

            except KeyboardInterrupt:
                raise
            except Exception as e:
                consecutive_failures += 1
                logger.error("Collection error (attempt %d/%d): %s",
                             consecutive_failures, MAX_RETRIES, e)

                if consecutive_failures >= MAX_RETRIES:
                    logger.warning(
                        "Max retries (%d) reached, backing off for %ds",
                        MAX_RETRIES, BACKOFF_DELAY,
                    )
                    time.sleep(BACKOFF_DELAY)
                    consecutive_failures = 0
                else:
                    time.sleep(RETRY_DELAY)
                continue

            time.sleep(POLLING_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Shutdown requested (Ctrl+C)")
    finally:
        logger.info("Closing database connection")
        conn.close()


def run_dashboard():
    """Start the FastAPI dashboard server."""
    from dashboard.app import app
    logger.info("Starting dashboard at http://%s:%d", DASHBOARD_HOST, DASHBOARD_PORT)
    uvicorn.run(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT, log_level="warning")


if __name__ == "__main__":
    # Start dashboard in background thread
    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()

    # Run collector loop in main thread
    run_loop()
