"""Standalone collector entrypoint for Docker container."""

import logging
import time

from config.settings import (
    POLLING_INTERVAL,
    DATABASE_URL,
    RETRY_DELAY,
    MAX_RETRIES,
    BACKOFF_DELAY,
    DATA_STALE_THRESHOLD,
    CLEANUP_INTERVAL,
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
    logger.info("Connecting to database: %s", DATABASE_URL.split('@')[-1])
    conn = init_db(DATABASE_URL)

    collector = ExchangeCollector()

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

                    exchanges = {}
                    for t in tickers:
                        ex = t["exchange"]
                        exchanges[ex] = exchanges.get(ex, 0) + 1
                    stats = ", ".join(f"{ex}={cnt}" for ex, cnt in sorted(exchanges.items()))
                    logger.info("Collected %d tickers (%s)", len(tickers), stats)

                    spreads = calc_spreads(tickers)
                    if spreads:
                        top = spreads[0]
                        logger.info(
                            "Top spread: %s gross=%.2f%% net=%.2f%% (rate=%.0f KRW/USDT)",
                            top["symbol"], top["gross_premium_pct"],
                            top["net_spread_pct"], top["implied_rate"],
                        )

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

                elapsed = time.monotonic() - last_success_time
                if elapsed > DATA_STALE_THRESHOLD:
                    logger.warning("DATA STALE: no successful collection for %.1f seconds", elapsed)

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


if __name__ == "__main__":
    run_loop()
