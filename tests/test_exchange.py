"""Tests for collectors.exchange module."""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from collectors.exchange import ExchangeCollector


MOCK_UPBIT_ORDER_BOOKS = {
    "BTC/KRW": {
        "bids": [[95000000, 0.5]],
        "asks": [[95100000, 0.3]],
    },
    "ETH/KRW": {
        "bids": [[5000000, 1.0]],
        "asks": [[5010000, 0.8]],
    },
}

MOCK_UPBIT_TICKERS = {
    "BTC/KRW": {
        "bid": None,
        "ask": None,
        "last": 95050000,
        "quoteVolume": 1000000,
        "datetime": "2026-04-06T12:00:00.000Z",
    },
    "ETH/KRW": {
        "bid": None,
        "ask": None,
        "last": 5005000,
        "quoteVolume": 500000,
        "datetime": "2026-04-06T12:00:00.000Z",
    },
}

MOCK_BINANCE_TICKERS = {
    "BTC/USDT": {
        "bid": 69000,
        "ask": 69100,
        "last": 69050,
        "quoteVolume": 500000,
        "datetime": "2026-04-06T12:00:00.000Z",
    },
    "ETH/USDT": {
        "bid": 3400,
        "ask": 3410,
        "last": 3405,
        "quoteVolume": 200000,
        "datetime": "2026-04-06T12:00:00.000Z",
    },
}


class TestUpbitCollector(unittest.TestCase):
    """Test Upbit collection uses order books for bid/ask."""

    def setUp(self):
        with patch("collectors.exchange.ccxt"):
            self.collector = ExchangeCollector()
        self.collector.upbit = MagicMock()
        self.collector.binance = MagicMock()

    @patch("collectors.exchange.UPBIT_SYMBOLS", ["BTC/KRW", "ETH/KRW"])
    def test_upbit_uses_order_books_for_bid_ask(self):
        """Upbit must call fetch_order_books AND fetch_tickers."""
        self.collector.upbit.fetch_order_books.return_value = MOCK_UPBIT_ORDER_BOOKS
        self.collector.upbit.fetch_tickers.return_value = MOCK_UPBIT_TICKERS

        results = self.collector.collect_upbit()

        self.collector.upbit.fetch_order_books.assert_called_once_with(
            ["BTC/KRW", "ETH/KRW"], limit=1
        )
        self.collector.upbit.fetch_tickers.assert_called_once_with(
            ["BTC/KRW", "ETH/KRW"]
        )
        self.assertEqual(len(results), 2)

    @patch("collectors.exchange.UPBIT_SYMBOLS", ["BTC/KRW"])
    def test_upbit_bid_ask_from_order_book(self):
        """bid/ask must come from order book, not tickers."""
        self.collector.upbit.fetch_order_books.return_value = {
            "BTC/KRW": {"bids": [[95000000, 0.5]], "asks": [[95100000, 0.3]]}
        }
        self.collector.upbit.fetch_tickers.return_value = {
            "BTC/KRW": {
                "bid": None, "ask": None, "last": 95050000,
                "quoteVolume": 1000000, "datetime": "2026-04-06T12:00:00.000Z",
            }
        }

        results = self.collector.collect_upbit()

        self.assertEqual(results[0]["bid_price"], 95000000.0)
        self.assertEqual(results[0]["ask_price"], 95100000.0)
        self.assertEqual(results[0]["last_price"], 95050000.0)

    @patch("collectors.exchange.UPBIT_SYMBOLS", ["BTC/KRW"])
    def test_upbit_api_failure_returns_empty(self):
        """API failure should return empty list, not crash."""
        self.collector.upbit.fetch_order_books.side_effect = Exception("API down")

        results = self.collector.collect_upbit()

        self.assertEqual(results, [])


class TestBinanceCollector(unittest.TestCase):
    """Test Binance collection uses only fetch_tickers."""

    def setUp(self):
        with patch("collectors.exchange.ccxt"):
            self.collector = ExchangeCollector()
        self.collector.upbit = MagicMock()
        self.collector.binance = MagicMock()

    @patch("collectors.exchange.BINANCE_SYMBOLS", ["BTC/USDT", "ETH/USDT"])
    def test_binance_uses_only_tickers(self):
        """Binance should only call fetch_tickers, not fetch_order_books."""
        self.collector.binance.fetch_tickers.return_value = MOCK_BINANCE_TICKERS

        results = self.collector.collect_binance()

        self.collector.binance.fetch_tickers.assert_called_once_with(
            ["BTC/USDT", "ETH/USDT"]
        )
        self.collector.binance.fetch_order_books.assert_not_called()
        self.assertEqual(len(results), 2)

    @patch("collectors.exchange.BINANCE_SYMBOLS", ["BTC/USDT"])
    def test_binance_bid_ask_from_tickers(self):
        """bid/ask come directly from tickers for Binance."""
        self.collector.binance.fetch_tickers.return_value = {
            "BTC/USDT": {
                "bid": 69000, "ask": 69100, "last": 69050,
                "quoteVolume": 500000, "datetime": "2026-04-06T12:00:00.000Z",
            }
        }

        results = self.collector.collect_binance()

        self.assertEqual(results[0]["bid_price"], 69000.0)
        self.assertEqual(results[0]["ask_price"], 69100.0)
        self.assertEqual(results[0]["last_price"], 69050.0)

    @patch("collectors.exchange.BINANCE_SYMBOLS", ["BTC/USDT"])
    def test_binance_api_failure_returns_empty(self):
        """API failure should return empty list, not crash."""
        self.collector.binance.fetch_tickers.side_effect = Exception("timeout")

        results = self.collector.collect_binance()

        self.assertEqual(results, [])


class TestDataNormalization(unittest.TestCase):
    """Test output format normalization."""

    def setUp(self):
        with patch("collectors.exchange.ccxt"):
            self.collector = ExchangeCollector()
        self.collector.upbit = MagicMock()
        self.collector.binance = MagicMock()

    @patch("collectors.exchange.UPBIT_SYMBOLS", ["BTC/KRW"])
    def test_upbit_symbol_is_base_only(self):
        """Symbol should be 'BTC', not 'BTC/KRW'."""
        self.collector.upbit.fetch_order_books.return_value = {
            "BTC/KRW": {"bids": [[95000000, 0.5]], "asks": [[95100000, 0.3]]}
        }
        self.collector.upbit.fetch_tickers.return_value = {
            "BTC/KRW": {
                "bid": None, "ask": None, "last": 95050000,
                "quoteVolume": 1000000, "datetime": "2026-04-06T12:00:00.000Z",
            }
        }

        results = self.collector.collect_upbit()

        self.assertEqual(results[0]["symbol"], "BTC")
        self.assertEqual(results[0]["exchange"], "upbit")

    @patch("collectors.exchange.BINANCE_SYMBOLS", ["ETH/USDT"])
    def test_binance_symbol_is_base_only(self):
        """Symbol should be 'ETH', not 'ETH/USDT'."""
        self.collector.binance.fetch_tickers.return_value = {
            "ETH/USDT": {
                "bid": 3400, "ask": 3410, "last": 3405,
                "quoteVolume": 200000, "datetime": "2026-04-06T12:00:00.000Z",
            }
        }

        results = self.collector.collect_binance()

        self.assertEqual(results[0]["symbol"], "ETH")
        self.assertEqual(results[0]["exchange"], "binance")

    @patch("collectors.exchange.UPBIT_SYMBOLS", ["BTC/KRW"])
    def test_timestamp_is_utc_datetime(self):
        """Timestamp should be a UTC datetime object."""
        self.collector.upbit.fetch_order_books.return_value = {
            "BTC/KRW": {"bids": [[95000000, 0.5]], "asks": [[95100000, 0.3]]}
        }
        self.collector.upbit.fetch_tickers.return_value = {
            "BTC/KRW": {
                "bid": None, "ask": None, "last": 95050000,
                "quoteVolume": 1000000, "datetime": "2026-04-06T12:00:00.000Z",
            }
        }

        results = self.collector.collect_upbit()

        ts = results[0]["timestamp"]
        self.assertIsInstance(ts, datetime)
        self.assertEqual(ts.tzinfo, timezone.utc)

    @patch("collectors.exchange.UPBIT_SYMBOLS", ["BTC/KRW"])
    def test_all_required_keys_present(self):
        """Each result dict must have all required keys."""
        self.collector.upbit.fetch_order_books.return_value = {
            "BTC/KRW": {"bids": [[95000000, 0.5]], "asks": [[95100000, 0.3]]}
        }
        self.collector.upbit.fetch_tickers.return_value = {
            "BTC/KRW": {
                "bid": None, "ask": None, "last": 95050000,
                "quoteVolume": 1000000, "datetime": "2026-04-06T12:00:00.000Z",
            }
        }

        results = self.collector.collect_upbit()
        required_keys = {"exchange", "symbol", "bid_price", "ask_price",
                         "last_price", "volume_24h", "timestamp"}

        self.assertEqual(set(results[0].keys()), required_keys)


class TestCollectAll(unittest.TestCase):
    """Test collect_all combines both exchanges."""

    def setUp(self):
        with patch("collectors.exchange.ccxt"):
            self.collector = ExchangeCollector()
        self.collector.upbit = MagicMock()
        self.collector.binance = MagicMock()

    @patch("collectors.exchange.BINANCE_SYMBOLS", ["BTC/USDT"])
    @patch("collectors.exchange.UPBIT_SYMBOLS", ["BTC/KRW"])
    def test_collect_all_combines_results(self):
        """collect_all should return data from both exchanges."""
        self.collector.upbit.fetch_order_books.return_value = {
            "BTC/KRW": {"bids": [[95000000, 0.5]], "asks": [[95100000, 0.3]]}
        }
        self.collector.upbit.fetch_tickers.return_value = {
            "BTC/KRW": {
                "bid": None, "ask": None, "last": 95050000,
                "quoteVolume": 1000000, "datetime": "2026-04-06T12:00:00.000Z",
            }
        }
        self.collector.binance.fetch_tickers.return_value = {
            "BTC/USDT": {
                "bid": 69000, "ask": 69100, "last": 69050,
                "quoteVolume": 500000, "datetime": "2026-04-06T12:00:00.000Z",
            }
        }

        results = self.collector.collect_all()

        exchanges = [r["exchange"] for r in results]
        self.assertIn("upbit", exchanges)
        self.assertIn("binance", exchanges)
        self.assertEqual(len(results), 2)

    @patch("collectors.exchange.BINANCE_SYMBOLS", ["BTC/USDT"])
    @patch("collectors.exchange.UPBIT_SYMBOLS", ["BTC/KRW"])
    def test_collect_all_partial_failure(self):
        """If one exchange fails, still get data from the other."""
        self.collector.upbit.fetch_order_books.side_effect = Exception("down")
        self.collector.binance.fetch_tickers.return_value = {
            "BTC/USDT": {
                "bid": 69000, "ask": 69100, "last": 69050,
                "quoteVolume": 500000, "datetime": "2026-04-06T12:00:00.000Z",
            }
        }

        results = self.collector.collect_all()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["exchange"], "binance")


if __name__ == "__main__":
    unittest.main()
