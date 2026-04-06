"""Exchange data collectors using ccxt.

Upbit: fetch_order_books for bid/ask + fetch_tickers for last/volume (2 calls)
Binance: fetch_tickers for everything (1 call)
"""

import logging
from datetime import datetime, timezone

import ccxt

from config.settings import UPBIT_SYMBOLS, BINANCE_SYMBOLS

logger = logging.getLogger(__name__)


class ExchangeCollector:
    def __init__(self):
        self.upbit = ccxt.upbit()
        self.binance = ccxt.binance()

    def collect_upbit(self) -> list[dict]:
        """Collect from Upbit using order books + tickers.

        Returns list of dicts with keys:
        exchange, symbol, bid_price, ask_price, last_price, volume_24h, timestamp
        """
        try:
            # Upbit fetch_tickers returns bid=None, ask=None
            # Must use fetch_order_books for bid/ask
            order_books = self.upbit.fetch_order_books(UPBIT_SYMBOLS, limit=1)
            tickers = self.upbit.fetch_tickers(UPBIT_SYMBOLS)
        except Exception as e:
            logger.error("Upbit collection failed: %s", e)
            return []

        results = []
        for symbol in UPBIT_SYMBOLS:
            try:
                ob = order_books.get(symbol)
                ticker = tickers.get(symbol)
                if ob is None or ticker is None:
                    logger.warning("Missing data for %s on Upbit", symbol)
                    continue

                bids = ob.get("bids", [])
                asks = ob.get("asks", [])
                bid_price = float(bids[0][0]) if bids else None
                ask_price = float(asks[0][0]) if asks else None

                # Parse timestamp
                dt_str = ticker.get("datetime")
                if dt_str:
                    ts = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                else:
                    ts = datetime.now(timezone.utc)

                base = symbol.split("/")[0]
                results.append({
                    "exchange": "upbit",
                    "symbol": base,
                    "bid_price": bid_price,
                    "ask_price": ask_price,
                    "last_price": float(ticker["last"]) if ticker.get("last") is not None else None,
                    "volume_24h": float(ticker["quoteVolume"]) if ticker.get("quoteVolume") is not None else None,
                    "timestamp": ts,
                })
            except Exception as e:
                logger.error("Error processing Upbit %s: %s", symbol, e)
                continue

        return results

    def collect_binance(self) -> list[dict]:
        """Collect from Binance using tickers only.

        Returns list of dicts with keys:
        exchange, symbol, bid_price, ask_price, last_price, volume_24h, timestamp
        """
        try:
            tickers = self.binance.fetch_tickers(BINANCE_SYMBOLS)
        except Exception as e:
            logger.error("Binance collection failed: %s", e)
            return []

        results = []
        for symbol in BINANCE_SYMBOLS:
            try:
                ticker = tickers.get(symbol)
                if ticker is None:
                    logger.warning("Missing data for %s on Binance", symbol)
                    continue

                dt_str = ticker.get("datetime")
                if dt_str:
                    ts = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                else:
                    ts = datetime.now(timezone.utc)

                base = symbol.split("/")[0]
                results.append({
                    "exchange": "binance",
                    "symbol": base,
                    "bid_price": float(ticker["bid"]) if ticker.get("bid") is not None else None,
                    "ask_price": float(ticker["ask"]) if ticker.get("ask") is not None else None,
                    "last_price": float(ticker["last"]) if ticker.get("last") is not None else None,
                    "volume_24h": float(ticker["quoteVolume"]) if ticker.get("quoteVolume") is not None else None,
                    "timestamp": ts,
                })
            except Exception as e:
                logger.error("Error processing Binance %s: %s", symbol, e)
                continue

        return results

    def collect_all(self) -> list[dict]:
        """Collect from both exchanges. Returns combined list."""
        upbit_data = self.collect_upbit()
        binance_data = self.collect_binance()
        return upbit_data + binance_data
