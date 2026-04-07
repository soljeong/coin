"""Graph-based arbitrage cycle detection using Bellman-Ford.

Models exchanges and coins as a directed graph where:
- Nodes: exchange:coin pairs (e.g. "upbit:BTC", "binance:ETH")
- Edges: intra-exchange trades or cross-exchange transfers
- Weights: -log(exchange_rate * (1 - fee)) for Bellman-Ford negative cycle detection

A negative-weight cycle in log-space = a profitable arbitrage cycle in real space.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from analysis.spread import calc_implied_rate, _build_price_map
from config.settings import (
    UPBIT_FEE,
    BINANCE_FEE,
    WITHDRAWAL_FEES,
    MAX_HOPS,
    MIN_NET_PROFIT_PCT,
    VOLUME_MIN_THRESHOLD,
)

logger = logging.getLogger(__name__)

# Fees per exchange for trading
EXCHANGE_FEES = {
    "upbit": UPBIT_FEE,
    "binance": BINANCE_FEE,
}

# Which coins can be transferred between exchanges
# For now, all coins are transferable; withdrawal fees from settings
TRANSFER_COINS = set(WITHDRAWAL_FEES.keys())


def build_graph(tickers: list[dict], implied_rate: float) -> tuple[list[str], list[tuple]]:
    """Build a directed graph from ticker data.

    Args:
        tickers: List of ticker dicts with exchange, symbol, bid_price, ask_price, volume_24h.
        implied_rate: KRW/USDT exchange rate for cross-currency edge weights.

    Returns:
        (nodes, edges) where:
        - nodes: list of node IDs like "upbit:BTC"
        - edges: list of (src, dst, weight, meta) tuples
          meta dict has: type, fee, rate, raw_rate
    """
    price_map = _build_price_map(tickers)
    nodes = set()
    edges = []

    # Collect all (exchange, symbol) pairs
    for (exchange, symbol), t in price_map.items():
        nodes.add(f"{exchange}:{symbol}")

    # Group tickers by exchange
    by_exchange: dict[str, list[dict]] = {}
    for t in tickers:
        by_exchange.setdefault(t["exchange"], []).append(t)

    # 1) Intra-exchange edges: trade coin A for coin B on the same exchange
    for exchange, exchange_tickers in by_exchange.items():
        fee = EXCHANGE_FEES.get(exchange, 0.001)
        for t_sell in exchange_tickers:
            for t_buy in exchange_tickers:
                if t_sell["symbol"] == t_buy["symbol"]:
                    continue

                bid_sell = t_sell["bid_price"]  # price we get when selling
                ask_buy = t_buy["ask_price"]    # price we pay when buying

                if not bid_sell or not ask_buy or ask_buy <= 0:
                    continue

                # Rate: how many units of coin_buy we get per unit of coin_sell
                # Sell 1 unit of A at bid_A, get bid_A in quote currency
                # Buy B at ask_B, get bid_A / ask_B units of B
                # After fee on both trades: * (1-fee)^2
                rate = (bid_sell / ask_buy) * ((1 - fee) ** 2)
                if rate <= 0:
                    continue

                weight = -math.log(rate)
                src = f"{exchange}:{t_sell['symbol']}"
                dst = f"{exchange}:{t_buy['symbol']}"
                edges.append((src, dst, weight, {
                    "type": "trade",
                    "exchange": exchange,
                    "fee": fee * 2,
                    "rate": rate,
                    "raw_rate": bid_sell / ask_buy,
                }))

    # 2) Cross-exchange transfer edges: send coin from one exchange to another
    symbols_by_exchange: dict[str, set] = {}
    for t in tickers:
        symbols_by_exchange.setdefault(t["exchange"], set()).add(t["symbol"])

    all_exchanges = list(symbols_by_exchange.keys())
    for i, ex_from in enumerate(all_exchanges):
        for ex_to in all_exchanges[i + 1:]:
            # Both directions
            common = symbols_by_exchange[ex_from] & symbols_by_exchange[ex_to]
            for symbol in common:
                t_from = price_map.get((ex_from, symbol))
                t_to = price_map.get((ex_to, symbol))
                if t_from is None or t_to is None:
                    continue

                # Withdrawal fee as fraction of 1 coin
                withdrawal_fee_coins = WITHDRAWAL_FEES.get(symbol, 0)

                # Direction: ex_from -> ex_to
                # When transferring, we lose withdrawal_fee_coins
                # Need to convert to a rate: effective coins received / coins sent
                # If sending 1 coin: receive (1 - withdrawal_fee_coins) ... but fee is in absolute coins
                # Use bid price to estimate fraction: fee_fraction = withdrawal_fee * ask_price_from / bid_price_from
                # Simpler: if we have 1 coin, we receive (1 - withdrawal_fee_coins) coins
                # But we also need to account for the price difference due to different quote currencies
                # upbit is KRW, binance is USDT — use implied_rate
                bid_from = t_from["bid_price"]
                ask_to = t_to["ask_price"]
                if not bid_from or bid_from <= 0 or not ask_to or ask_to <= 0:
                    continue

                # Price ratio accounting for different quote currencies
                if ex_from == "upbit" and ex_to == "binance":
                    # KRW -> USDT: divide by implied_rate
                    cross_rate = (bid_from / implied_rate) / ask_to
                elif ex_from == "binance" and ex_to == "upbit":
                    # USDT -> KRW: multiply by implied_rate
                    cross_rate = (bid_from * implied_rate) / ask_to
                else:
                    cross_rate = bid_from / ask_to

                # Apply withdrawal fee
                if bid_from > 0:
                    fee_fraction = withdrawal_fee_coins * ask_to / bid_from if ex_from == "binance" else withdrawal_fee_coins * ask_to * implied_rate / bid_from
                    # Simpler approach: just use coin-based fee
                    # Assume sending 1 coin, receive (1 - fee_coins/1) = needs amount context
                    # For graph purposes, use a fixed fraction estimate
                    fee_fraction = min(withdrawal_fee_coins * (ask_to if ex_to == "binance" else ask_to / implied_rate) / max(bid_from / (implied_rate if ex_from == "upbit" else 1), 0.0001), 0.05)

                rate_from_to = cross_rate * (1 - min(fee_fraction, 0.05))
                if rate_from_to <= 0:
                    continue

                src = f"{ex_from}:{symbol}"
                dst = f"{ex_to}:{symbol}"
                weight = -math.log(rate_from_to)
                edges.append((src, dst, weight, {
                    "type": "transfer",
                    "fee": fee_fraction,
                    "rate": rate_from_to,
                    "withdrawal_fee_coins": withdrawal_fee_coins,
                }))

                # Reverse direction: ex_to -> ex_from
                bid_to = t_to["bid_price"]
                ask_from = t_from["ask_price"]
                if not bid_to or bid_to <= 0 or not ask_from or ask_from <= 0:
                    continue

                if ex_to == "upbit" and ex_from == "binance":
                    cross_rate_rev = (bid_to / implied_rate) / ask_from
                elif ex_to == "binance" and ex_from == "upbit":
                    cross_rate_rev = (bid_to * implied_rate) / ask_from
                else:
                    cross_rate_rev = bid_to / ask_from

                fee_fraction_rev = min(withdrawal_fee_coins * (ask_from if ex_from == "binance" else ask_from / implied_rate) / max(bid_to / (implied_rate if ex_to == "upbit" else 1), 0.0001), 0.05)

                rate_to_from = cross_rate_rev * (1 - min(fee_fraction_rev, 0.05))
                if rate_to_from <= 0:
                    continue

                edges.append((f"{ex_to}:{symbol}", f"{ex_from}:{symbol}", -math.log(rate_to_from), {
                    "type": "transfer",
                    "fee": fee_fraction_rev,
                    "rate": rate_to_from,
                    "withdrawal_fee_coins": withdrawal_fee_coins,
                }))

    return sorted(nodes), edges


def find_arbitrage_cycles(
    nodes: list[str],
    edges: list[tuple],
    max_hops: int = MAX_HOPS,
) -> list[dict]:
    """Find negative-weight cycles using Bellman-Ford with hop limit.

    Returns list of opportunities sorted by profit descending:
    [{ path: [...], hops: int, gross_spread: float, net_profit: float,
       total_fees: float, risk_level: str }]
    """
    opportunities = []
    node_idx = {n: i for i, n in enumerate(nodes)}
    n = len(nodes)

    if n == 0:
        return []

    # Run Bellman-Ford from each node as source
    for source in range(n):
        dist = [float("inf")] * n
        pred = [-1] * n
        hops = [0] * n
        dist[source] = 0.0

        # Relax edges up to max_hops times
        for iteration in range(min(max_hops, n - 1)):
            updated = False
            for src_name, dst_name, weight, meta in edges:
                u = node_idx.get(src_name)
                v = node_idx.get(dst_name)
                if u is None or v is None:
                    continue
                if dist[u] + weight < dist[v] and hops[u] < max_hops:
                    dist[v] = dist[u] + weight
                    pred[v] = u
                    hops[v] = hops[u] + 1
                    updated = True
            if not updated:
                break

        # Check for negative cycles (one more relaxation)
        for src_name, dst_name, weight, meta in edges:
            u = node_idx.get(src_name)
            v = node_idx.get(dst_name)
            if u is None or v is None:
                continue
            if dist[u] + weight < dist[v] and hops[u] < max_hops:
                # Found negative cycle — trace it back
                cycle = _trace_cycle(pred, v, nodes, max_hops)
                if cycle and len(cycle) >= 2:
                    # Calculate actual profit from the cycle
                    opp = _evaluate_cycle(cycle, edges, node_idx)
                    if opp and opp["net_profit"] >= MIN_NET_PROFIT_PCT:
                        # Deduplicate: normalize cycle
                        normalized = _normalize_cycle(cycle)
                        opp["path"] = normalized
                        opp["hops"] = len(normalized)
                        opportunities.append(opp)

    # Deduplicate by normalized path
    seen = set()
    unique = []
    for opp in opportunities:
        key = "->".join(opp["path"])
        if key not in seen:
            seen.add(key)
            unique.append(opp)

    unique.sort(key=lambda x: x["net_profit"], reverse=True)
    return unique


def _trace_cycle(pred: list[int], start: int, nodes: list[str], max_hops: int) -> list[str]:
    """Trace back through predecessors to find the cycle."""
    visited = set()
    current = start
    path = []

    # Walk back to find a node in the cycle
    for _ in range(max_hops + 1):
        if current in visited:
            break
        visited.add(current)
        current = pred[current]
        if current == -1:
            return []

    # current is now in the cycle; trace the full cycle
    cycle_start = current
    cycle = [nodes[cycle_start]]
    current = pred[cycle_start]
    steps = 0
    while current != cycle_start and steps < max_hops:
        cycle.append(nodes[current])
        current = pred[current]
        steps += 1
        if current == -1:
            return []

    cycle.reverse()
    return cycle


def _evaluate_cycle(
    cycle: list[str],
    edges: list[tuple],
    node_idx: dict[str, int],
) -> Optional[dict]:
    """Calculate profit/fees for a cycle path."""
    # Build edge lookup: (src, dst) -> best edge
    edge_map: dict[tuple, tuple] = {}
    for src, dst, weight, meta in edges:
        key = (src, dst)
        if key not in edge_map or weight < edge_map[key][2]:
            edge_map[key] = (src, dst, weight, meta)

    total_weight = 0.0
    total_fee = 0.0

    for i in range(len(cycle)):
        src = cycle[i]
        dst = cycle[(i + 1) % len(cycle)]
        edge = edge_map.get((src, dst))
        if edge is None:
            return None
        _, _, weight, meta = edge
        total_weight += weight
        total_fee += meta.get("fee", 0)

    # Convert from log-space: profit = exp(-total_weight) - 1
    gross_multiplier = math.exp(-total_weight + total_fee)  # before fees
    net_multiplier = math.exp(-total_weight)  # after fees (fees already in weights)

    gross_spread = (gross_multiplier - 1) * 100  # percentage
    net_profit = (net_multiplier - 1) * 100

    # Risk assessment based on profit margin and hop count
    risk_level = _assess_risk(net_profit, len(cycle))

    return {
        "gross_spread": round(gross_spread, 4),
        "net_profit": round(net_profit, 4),
        "total_fees": round(total_fee * 100, 4),  # as percentage
        "risk_level": risk_level,
    }


def _normalize_cycle(cycle: list[str]) -> list[str]:
    """Normalize cycle so it starts from the lexicographically smallest node."""
    if not cycle:
        return cycle
    min_idx = cycle.index(min(cycle))
    return cycle[min_idx:] + cycle[:min_idx]


def _assess_risk(net_profit_pct: float, hops: int) -> str:
    """Assess risk level of an arbitrage opportunity.

    LOW: high profit, few hops
    MED: moderate profit or moderate hops
    HIGH: thin margin or many hops
    """
    if net_profit_pct >= 1.0 and hops <= 3:
        return "LOW"
    elif net_profit_pct >= 0.5 or hops <= 3:
        return "MED"
    else:
        return "HIGH"


def detect_opportunities(tickers: list[dict]) -> list[dict]:
    """Main entry point: detect arbitrage opportunities from ticker data.

    Args:
        tickers: Latest ticker data from collectors.

    Returns:
        List of opportunity dicts ready for DB insertion:
        [{ path, hops, gross_spread, net_profit, total_fees, risk_level, timestamp }]
    """
    if not tickers:
        return []

    price_map = _build_price_map(tickers)
    implied_rate = calc_implied_rate(price_map)

    if implied_rate is None:
        logger.warning("Cannot detect opportunities: no implied rate")
        return []

    nodes, edges = build_graph(tickers, implied_rate)

    if not nodes or not edges:
        logger.debug("Empty graph, no opportunities")
        return []

    opportunities = find_arbitrage_cycles(nodes, edges)

    now = datetime.now(timezone.utc)
    for opp in opportunities:
        opp["path"] = "->".join(opp["path"])
        opp["timestamp"] = now

    logger.info(
        "Detected %d opportunities (min %.2f%%)",
        len(opportunities),
        MIN_NET_PROFIT_PCT,
    )
    for opp in opportunities[:3]:
        logger.info(
            "  %s (%d hops): net=%.2f%% gross=%.2f%% risk=%s",
            opp["path"], opp["hops"], opp["net_profit"],
            opp["gross_spread"], opp["risk_level"],
        )

    return opportunities
