"""Bridge coin spread calculator.

Calculates the implied KRW/USDT exchange rate using bridge coins (XRP, XLM),
then computes kimchi premium and net arbitrage spread for all monitored coins.
"""

import logging
from typing import Optional

from config.settings import (
    BRIDGE_COINS,
    UPBIT_FEE,
    BINANCE_FEE,
    WITHDRAWAL_FEES,
)

logger = logging.getLogger(__name__)


def _build_price_map(tickers: list[dict]) -> dict[tuple[str, str], dict]:
    """Index tickers by (exchange, symbol) for O(1) lookup.

    Returns dict mapping (exchange, symbol) -> ticker dict.
    """
    price_map = {}
    for t in tickers:
        key = (t["exchange"], t["symbol"])
        price_map[key] = t
    return price_map


def calc_implied_rate(price_map: dict[tuple[str, str], dict]) -> Optional[float]:
    """Calculate implied KRW/USDT rate from bridge coins.

    For each bridge coin with data on both exchanges:
      implied_rate = upbit_bid (KRW) / binance_ask (USDT)

    Returns the average implied rate across available bridge coins,
    or None if no bridge coin has data on both exchanges.
    """
    rates = []
    for coin in BRIDGE_COINS:
        upbit = price_map.get(("upbit", coin))
        binance = price_map.get(("binance", coin))
        if upbit is None or binance is None:
            continue

        upbit_bid = upbit["bid_price"]
        binance_ask = binance["ask_price"]
        if not upbit_bid or not binance_ask or binance_ask <= 0:
            continue

        # Deduct withdrawal fee impact on the bridge coin rate
        withdrawal_fee = WITHDRAWAL_FEES.get(coin, 0)
        # Effective coins received after withdrawal = 1 - (fee / amount bought)
        # For rate calc, assume buying 1 USDT worth: amount = 1/binance_ask coins
        # Fee fraction = withdrawal_fee * binance_ask (in USDT terms)
        # Simpler: rate after fees on 1 coin transfer
        if binance_ask > 0:
            fee_fraction = withdrawal_fee * binance_ask  # fee in USDT terms
        else:
            fee_fraction = 0

        # Raw implied rate (KRW per USDT)
        raw_rate = upbit_bid / binance_ask
        rates.append({
            "coin": coin,
            "raw_rate": raw_rate,
            "upbit_bid": upbit_bid,
            "binance_ask": binance_ask,
            "withdrawal_fee_usdt": fee_fraction,
        })

    if not rates:
        logger.warning("No bridge coin data available for implied rate")
        return None

    avg_rate = sum(r["raw_rate"] for r in rates) / len(rates)
    for r in rates:
        logger.debug(
            "Bridge %s: upbit_bid=%.2f, binance_ask=%.4f, implied_rate=%.2f",
            r["coin"], r["upbit_bid"], r["binance_ask"], r["raw_rate"],
        )
    logger.info("Implied KRW/USDT rate: %.2f (from %d bridge coins)", avg_rate, len(rates))
    return avg_rate


def calc_spreads(
    tickers: list[dict],
    implied_rate: Optional[float] = None,
) -> list[dict]:
    """Calculate kimchi premium and net spread for all coins.

    Args:
        tickers: Latest ticker data from get_latest_tickers().
        implied_rate: Pre-calculated implied KRW/USDT rate.
                      If None, calculates from bridge coins in tickers.

    Returns list of dicts sorted by net_spread descending:
        symbol, upbit_bid, upbit_ask, binance_bid, binance_ask,
        implied_rate, gross_premium_pct, total_fee_pct, net_spread_pct
    """
    price_map = _build_price_map(tickers)

    if implied_rate is None:
        implied_rate = calc_implied_rate(price_map)
    if implied_rate is None:
        return []

    results = []
    # Get unique symbols
    symbols = set(t["symbol"] for t in tickers)

    for symbol in symbols:
        upbit = price_map.get(("upbit", symbol))
        binance = price_map.get(("binance", symbol))
        if upbit is None or binance is None:
            continue

        upbit_bid = upbit["bid_price"]
        upbit_ask = upbit["ask_price"]
        binance_bid = binance["bid_price"]
        binance_ask = binance["ask_price"]

        if not all([upbit_bid, binance_ask, binance_ask > 0]):
            continue

        # Gross kimchi premium: how much more expensive on Upbit vs Binance
        # (Upbit price in KRW) / (Binance price in USDT * implied_rate) - 1
        upbit_in_implied_usdt = upbit_bid / implied_rate
        gross_premium_pct = (upbit_in_implied_usdt / binance_ask - 1) * 100

        # Fee breakdown for buy-on-Binance, sell-on-Upbit arbitrage:
        # 1. Buy on Binance: BINANCE_FEE
        # 2. Sell on Upbit: UPBIT_FEE
        total_fee_pct = (BINANCE_FEE + UPBIT_FEE) * 100

        # Net spread after trading fees (withdrawal fee not included here
        # as it varies by coin amount; it's captured in the implied rate)
        net_spread_pct = gross_premium_pct - total_fee_pct

        results.append({
            "symbol": symbol,
            "upbit_bid": upbit_bid,
            "upbit_ask": upbit_ask,
            "binance_bid": binance_bid,
            "binance_ask": binance_ask,
            "implied_rate": implied_rate,
            "gross_premium_pct": round(gross_premium_pct, 4),
            "total_fee_pct": round(total_fee_pct, 4),
            "net_spread_pct": round(net_spread_pct, 4),
        })

    results.sort(key=lambda x: x["net_spread_pct"], reverse=True)
    return results
