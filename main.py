"""Entry point: polling loop that collects exchange data and stores it."""

import logging
import time
from datetime import datetime, timezone

from config.settings import (
    POLLING_INTERVAL,
    DB_PATH,
    RETRY_DELAY,
    MAX_RETRIES,
    BACKOFF_DELAY,
    DATA_STALE_THRESHOLD,
    CLEANUP_INTERVAL,
)
from storage.db import init_db, insert_tickers, cleanup_old_data
from collectors.exchange import ExchangeCollector

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


if __name__ == "__main__":
    run_loop()
