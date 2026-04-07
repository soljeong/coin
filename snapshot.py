"""One-shot snapshot: collect once, analyze in detail.

Usage: python snapshot.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone

from collectors.exchange import ExchangeCollector
from analysis.spread import calc_implied_rate, calc_spreads, _build_price_map
from config.settings import (
    TARGET_COINS, BRIDGE_COINS, UPBIT_FEE, BINANCE_FEE, WITHDRAWAL_FEES,
)


def fmt_krw(v):
    """Format KRW price with comma separators."""
    if v is None:
        return "N/A"
    if v >= 1_000_000:
        return f"{v:>15,.0f}"
    return f"{v:>15,.2f}"


def fmt_usdt(v):
    """Format USDT price."""
    if v is None:
        return "N/A"
    if v >= 100:
        return f"{v:>12,.2f}"
    return f"{v:>12,.4f}"


def fmt_pct(v):
    return f"{v:>+7.2f}%"


def fmt_vol(v):
    if v is None:
        return "N/A"
    if v >= 1e12:
        return f"{v/1e12:.1f}T"
    if v >= 1e9:
        return f"{v/1e9:.1f}B"
    if v >= 1e6:
        return f"{v/1e6:.1f}M"
    if v >= 1e3:
        return f"{v/1e3:.1f}K"
    return f"{v:.0f}"


def main():
    print("=" * 80)
    print("  SNAPSHOT: Cross-Exchange Arbitrage Analysis")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)

    # --- Collect ---
    print("\n[1/4] Collecting data from exchanges...")
    collector = ExchangeCollector()
    upbit_data = collector.collect_upbit()
    binance_data = collector.collect_binance()
    all_data = upbit_data + binance_data

    print(f"  Upbit:   {len(upbit_data)} coins collected")
    print(f"  Binance: {len(binance_data)} coins collected")

    if not upbit_data or not binance_data:
        print("\n  ERROR: Failed to collect from one or both exchanges. Aborting.")
        sys.exit(1)

    price_map = _build_price_map(all_data)

    # --- Raw Prices ---
    print("\n" + "=" * 80)
    print("  [2/4] RAW PRICE COMPARISON")
    print("=" * 80)

    header = f"{'Coin':>6} | {'Upbit Bid(KRW)':>15} {'Upbit Ask(KRW)':>15} {'Spread':>7} | {'Binance Bid($)':>12} {'Binance Ask($)':>12} {'Spread':>7} | {'Vol(Upbit)':>10} {'Vol(Binance)':>10}"
    print(header)
    print("-" * len(header))

    for coin in TARGET_COINS:
        u = price_map.get(("upbit", coin))
        b = price_map.get(("binance", coin))
        if u and b:
            u_spread = (u["ask_price"] - u["bid_price"]) / u["bid_price"] * 100
            b_spread = (b["ask_price"] - b["bid_price"]) / b["bid_price"] * 100
            print(
                f"{coin:>6} |"
                f" {fmt_krw(u['bid_price'])} {fmt_krw(u['ask_price'])} {fmt_pct(u_spread)} |"
                f" {fmt_usdt(b['bid_price'])} {fmt_usdt(b['ask_price'])} {fmt_pct(b_spread)} |"
                f" {fmt_vol(u.get('volume_24h')):>10} {fmt_vol(b.get('volume_24h')):>10}"
            )

    # --- Bridge Coin / Implied Rate ---
    print("\n" + "=" * 80)
    print("  [3/4] BRIDGE COIN ANALYSIS (Implied KRW/USDT Rate)")
    print("=" * 80)

    rates = []
    for coin in BRIDGE_COINS:
        u = price_map.get(("upbit", coin))
        b = price_map.get(("binance", coin))
        if u and b and b["ask_price"] > 0:
            raw_rate = u["bid_price"] / b["ask_price"]
            # Withdrawal fee impact
            w_fee = WITHDRAWAL_FEES.get(coin, 0)
            w_fee_usdt = w_fee * b["ask_price"]
            # Effective rate considering withdrawal fee on 100 USDT transfer
            coins_bought = 100 / b["ask_price"]
            coins_received = coins_bought - w_fee
            krw_received = coins_received * u["bid_price"]
            effective_rate = krw_received / 100  # KRW per USDT after fees

            rates.append({
                "coin": coin,
                "raw_rate": raw_rate,
                "effective_rate": effective_rate,
                "upbit_bid": u["bid_price"],
                "binance_ask": b["ask_price"],
                "w_fee": w_fee,
                "w_fee_usdt": w_fee_usdt,
            })
            print(f"\n  {coin}:")
            print(f"    Upbit Bid:        {fmt_krw(u['bid_price'])} KRW")
            print(f"    Binance Ask:      {fmt_usdt(b['ask_price'])} USDT")
            print(f"    Raw Rate:         {raw_rate:,.2f} KRW/USDT")
            print(f"    Withdrawal Fee:   {w_fee} {coin} (~{w_fee_usdt:.2f} USDT)")
            print(f"    Effective Rate:   {effective_rate:,.2f} KRW/USDT (on 100 USDT transfer)")

    if rates:
        avg_raw = sum(r["raw_rate"] for r in rates) / len(rates)
        avg_eff = sum(r["effective_rate"] for r in rates) / len(rates)
        rate_diff = abs(rates[0]["raw_rate"] - rates[-1]["raw_rate"]) if len(rates) > 1 else 0
        print(f"\n  Average Raw Rate:       {avg_raw:,.2f} KRW/USDT")
        print(f"  Average Effective Rate: {avg_eff:,.2f} KRW/USDT")
        if len(rates) > 1:
            print(f"  Rate Divergence:        {rate_diff:,.2f} KRW ({rate_diff/avg_raw*100:.2f}%)")

    # --- Spread Analysis ---
    print("\n" + "=" * 80)
    print("  [4/4] ARBITRAGE SPREAD ANALYSIS")
    print(f"  Fees: Upbit {UPBIT_FEE*100:.2f}% + Binance {BINANCE_FEE*100:.2f}% = {(UPBIT_FEE+BINANCE_FEE)*100:.2f}%")
    print("=" * 80)

    spreads = calc_spreads(all_data)

    if not spreads:
        print("\n  No spread data available.")
        return

    header2 = f"{'#':>2} {'Coin':>6} | {'Gross Premium':>13} {'Fees':>7} {'Net Spread':>11} | {'Direction'}"
    print(header2)
    print("-" * len(header2))

    profitable = 0
    for i, s in enumerate(spreads, 1):
        direction = "BUY Binance -> SELL Upbit" if s["net_spread_pct"] > 0 else "no arb"
        marker = " <<<" if s["net_spread_pct"] > 0 else ""
        if s["net_spread_pct"] > 0:
            profitable += 1
        print(
            f"{i:>2} {s['symbol']:>6} |"
            f" {fmt_pct(s['gross_premium_pct']):>13}"
            f" {fmt_pct(s['total_fee_pct']):>7}"
            f" {fmt_pct(s['net_spread_pct']):>11}"
            f" | {direction}{marker}"
        )

    # --- Summary ---
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    best = spreads[0]
    worst = spreads[-1]
    avg_net = sum(s["net_spread_pct"] for s in spreads) / len(spreads)

    print(f"  Coins analyzed:   {len(spreads)}")
    print(f"  Profitable:       {profitable}/{len(spreads)}")
    print(f"  Best opportunity: {best['symbol']} at {fmt_pct(best['net_spread_pct'])} net")
    print(f"  Worst:            {worst['symbol']} at {fmt_pct(worst['net_spread_pct'])} net")
    print(f"  Average net:      {fmt_pct(avg_net)}")
    print(f"  Implied Rate:     {best['implied_rate']:,.2f} KRW/USDT")

    # Quick profitability estimate for best coin
    if best["net_spread_pct"] > 0:
        print(f"\n  --- Quick Estimate: {best['symbol']} ---")
        for capital_usdt in [100, 1000, 10000]:
            profit_usdt = capital_usdt * best["net_spread_pct"] / 100
            profit_krw = profit_usdt * best["implied_rate"]
            print(f"  ${capital_usdt:>6,} USDT -> ~${profit_usdt:>8,.2f} USDT ({profit_krw:>10,.0f} KRW) profit")
    else:
        print(f"\n  No profitable arbitrage detected at this moment.")
        print(f"  The market premium is too small to cover trading fees.")

    print()


if __name__ == "__main__":
    main()
