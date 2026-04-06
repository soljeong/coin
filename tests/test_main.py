"""Tests for main.py polling loop."""

import time
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone

import pytest

from main import run_loop
from config.settings import CLEANUP_INTERVAL


def _make_tickers():
    """Return sample ticker data from both exchanges."""
    now = datetime.now(timezone.utc)
    return [
        {"exchange": "upbit", "symbol": "BTC", "bid_price": 95000000.0,
         "ask_price": 95100000.0, "last_price": 95050000.0,
         "volume_24h": 1000000.0, "timestamp": now},
        {"exchange": "upbit", "symbol": "ETH", "bid_price": 5000000.0,
         "ask_price": 5010000.0, "last_price": 5005000.0,
         "volume_24h": 500000.0, "timestamp": now},
        {"exchange": "binance", "symbol": "BTC", "bid_price": 68000.0,
         "ask_price": 68050.0, "last_price": 68025.0,
         "volume_24h": 2000000.0, "timestamp": now},
    ]


class TestMainLoop:
    """Tests for the main polling loop."""

    @patch("main.time")
    @patch("main.ExchangeCollector")
    @patch("main.cleanup_old_data")
    @patch("main.insert_tickers")
    @patch("main.init_db")
    def test_collects_and_stores(self, mock_init_db, mock_insert, mock_cleanup,
                                  mock_collector_cls, mock_time):
        """Loop collects data and inserts into DB."""
        conn = MagicMock()
        mock_init_db.return_value = conn

        collector = MagicMock()
        tickers = _make_tickers()
        # Return data once, then raise KeyboardInterrupt to exit
        collector.collect_all.side_effect = [tickers, KeyboardInterrupt]
        mock_collector_cls.return_value = collector

        mock_time.monotonic.return_value = 100.0
        mock_time.sleep = MagicMock()

        run_loop()

        mock_init_db.assert_called_once()
        mock_insert.assert_called_once_with(conn, tickers)
        conn.close.assert_called_once()

    @patch("main.time")
    @patch("main.ExchangeCollector")
    @patch("main.cleanup_old_data")
    @patch("main.insert_tickers")
    @patch("main.init_db")
    def test_empty_collection_not_inserted(self, mock_init_db, mock_insert,
                                            mock_cleanup, mock_collector_cls, mock_time):
        """Empty collector result should not call insert_tickers."""
        conn = MagicMock()
        mock_init_db.return_value = conn

        collector = MagicMock()
        collector.collect_all.side_effect = [[], KeyboardInterrupt]
        mock_collector_cls.return_value = collector

        mock_time.monotonic.return_value = 100.0
        mock_time.sleep = MagicMock()

        run_loop()

        mock_insert.assert_not_called()

    @patch("main.time")
    @patch("main.ExchangeCollector")
    @patch("main.cleanup_old_data")
    @patch("main.insert_tickers")
    @patch("main.init_db")
    def test_retry_on_failure(self, mock_init_db, mock_insert, mock_cleanup,
                               mock_collector_cls, mock_time):
        """On exception, retries with RETRY_DELAY then resumes."""
        conn = MagicMock()
        mock_init_db.return_value = conn

        collector = MagicMock()
        tickers = _make_tickers()
        # Fail once, succeed once, then exit
        collector.collect_all.side_effect = [
            RuntimeError("network error"),
            tickers,
            KeyboardInterrupt,
        ]
        mock_collector_cls.return_value = collector

        mock_time.monotonic.return_value = 100.0
        mock_time.sleep = MagicMock()

        run_loop()

        # After failure: sleep(RETRY_DELAY=10), after success: sleep(POLLING_INTERVAL=3)
        sleep_calls = mock_time.sleep.call_args_list
        assert call(10) in sleep_calls  # RETRY_DELAY
        assert call(3) in sleep_calls   # POLLING_INTERVAL
        # Data should be inserted on the successful attempt
        mock_insert.assert_called_once_with(conn, tickers)

    @patch("main.time")
    @patch("main.ExchangeCollector")
    @patch("main.cleanup_old_data")
    @patch("main.insert_tickers")
    @patch("main.init_db")
    def test_backoff_after_max_retries(self, mock_init_db, mock_insert, mock_cleanup,
                                        mock_collector_cls, mock_time):
        """After MAX_RETRIES consecutive failures, backoff for BACKOFF_DELAY."""
        conn = MagicMock()
        mock_init_db.return_value = conn

        collector = MagicMock()
        # Fail 3 times (MAX_RETRIES), then exit
        collector.collect_all.side_effect = [
            RuntimeError("err1"),
            RuntimeError("err2"),
            RuntimeError("err3"),
            KeyboardInterrupt,
        ]
        mock_collector_cls.return_value = collector

        mock_time.monotonic.return_value = 100.0
        mock_time.sleep = MagicMock()

        run_loop()

        sleep_calls = mock_time.sleep.call_args_list
        # First two failures: RETRY_DELAY each
        assert sleep_calls[0] == call(10)
        assert sleep_calls[1] == call(10)
        # Third failure hits MAX_RETRIES: BACKOFF_DELAY
        assert sleep_calls[2] == call(60)

    @patch("main.time")
    @patch("main.ExchangeCollector")
    @patch("main.cleanup_old_data")
    @patch("main.insert_tickers")
    @patch("main.init_db")
    def test_data_stale_warning(self, mock_init_db, mock_insert, mock_cleanup,
                                 mock_collector_cls, mock_time):
        """Warning logged when data is stale (no success beyond threshold)."""
        conn = MagicMock()
        mock_init_db.return_value = conn

        collector = MagicMock()
        # Return empty (no success update), then exit
        collector.collect_all.side_effect = [[], KeyboardInterrupt]
        mock_collector_cls.return_value = collector

        # Simulate time passing beyond DATA_STALE_THRESHOLD (15s)
        mock_time.monotonic.side_effect = [
            0.0,    # last_cleanup_time init
            0.0,    # last_success_time init (unused, set at top)
            20.0,   # elapsed check: monotonic() - last_success_time
            20.0,   # cleanup interval check
        ]
        mock_time.sleep = MagicMock()

        with patch("main.logger") as mock_logger:
            run_loop()
            # Check that a DATA STALE warning was logged
            stale_calls = [
                c for c in mock_logger.warning.call_args_list
                if "DATA STALE" in str(c)
            ]
            assert len(stale_calls) >= 1

    @patch("main.time")
    @patch("main.ExchangeCollector")
    @patch("main.cleanup_old_data")
    @patch("main.insert_tickers")
    @patch("main.init_db")
    def test_periodic_cleanup(self, mock_init_db, mock_insert, mock_cleanup,
                               mock_collector_cls, mock_time):
        """cleanup_old_data runs again after CLEANUP_INTERVAL."""
        conn = MagicMock()
        mock_init_db.return_value = conn

        collector = MagicMock()
        tickers = _make_tickers()
        collector.collect_all.side_effect = [tickers, KeyboardInterrupt]
        mock_collector_cls.return_value = collector

        # First monotonic calls for init, then jump past CLEANUP_INTERVAL
        mock_time.monotonic.side_effect = [
            0.0,                    # last_success_time init
            0.0,                    # last_cleanup_time init
            CLEANUP_INTERVAL + 1,  # inside loop: last_success_time update
            CLEANUP_INTERVAL + 1,  # elapsed check
            CLEANUP_INTERVAL + 1,  # cleanup interval check
            CLEANUP_INTERVAL + 1,  # new last_cleanup_time
        ]
        mock_time.sleep = MagicMock()

        run_loop()

        # cleanup_old_data called: once at startup + once periodic = 2
        assert mock_cleanup.call_count == 2

    @patch("main.time")
    @patch("main.ExchangeCollector")
    @patch("main.cleanup_old_data")
    @patch("main.insert_tickers")
    @patch("main.init_db")
    def test_graceful_shutdown(self, mock_init_db, mock_insert, mock_cleanup,
                                mock_collector_cls, mock_time):
        """KeyboardInterrupt triggers graceful shutdown and DB close."""
        conn = MagicMock()
        mock_init_db.return_value = conn

        collector = MagicMock()
        collector.collect_all.side_effect = KeyboardInterrupt
        mock_collector_cls.return_value = collector

        mock_time.monotonic.return_value = 100.0
        mock_time.sleep = MagicMock()

        run_loop()

        conn.close.assert_called_once()

    @patch("main.time")
    @patch("main.ExchangeCollector")
    @patch("main.cleanup_old_data")
    @patch("main.insert_tickers")
    @patch("main.init_db")
    def test_collection_stats_logging(self, mock_init_db, mock_insert, mock_cleanup,
                                       mock_collector_cls, mock_time):
        """Logs per-exchange counts after successful collection."""
        conn = MagicMock()
        mock_init_db.return_value = conn

        collector = MagicMock()
        tickers = _make_tickers()  # 2 upbit + 1 binance
        collector.collect_all.side_effect = [tickers, KeyboardInterrupt]
        mock_collector_cls.return_value = collector

        mock_time.monotonic.return_value = 100.0
        mock_time.sleep = MagicMock()

        with patch("main.logger") as mock_logger:
            run_loop()
            # logger.info is called with format string + args, not pre-formatted
            stats_logged = any(
                len(c.args) >= 3 and c.args[1] == 3
                for c in mock_logger.info.call_args_list
            )
            assert stats_logged, (
                f"Expected stats log with 3 tickers, got: "
                f"{mock_logger.info.call_args_list}"
            )
