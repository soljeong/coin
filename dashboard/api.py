"""REST API + SSE + What-If endpoints for the arbitrage monitor dashboard."""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from storage.db import get_latest_tickers, get_latest_opportunities, get_opportunity_history, get_db_size
from analysis.spread import calc_spreads, calc_implied_rate, _build_price_map
from config.settings import (
    POLLING_INTERVAL, TARGET_COINS,
    UPBIT_FEE, BINANCE_FEE, WITHDRAWAL_FEES,
)

router = APIRouter()


# --- REST endpoints ---

@router.get("/opportunities")
async def opportunities(request: Request, limit: int = 20):
    """Get latest arbitrage opportunities."""
    conn = request.app.state.db
    opps = get_latest_opportunities(conn, limit=limit)
    return {"opportunities": opps}


@router.get("/spreads")
async def spreads(request: Request):
    """Get current kimchi premium spreads for all coins."""
    conn = request.app.state.db
    tickers = get_latest_tickers(conn)
    spread_data = calc_spreads(tickers)
    return {"spreads": spread_data}


@router.get("/history")
async def history(request: Request, hours: int = 24):
    """Get opportunity history for the given time window."""
    conn = request.app.state.db
    hist = get_opportunity_history(conn, hours=hours)
    return {"history": hist}


@router.get("/status")
async def status(request: Request):
    """Get system status information."""
    conn = request.app.state.db

    ticker_count = conn.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]

    row = conn.execute("SELECT MAX(timestamp) FROM tickers").fetchone()
    last_update = row[0] if row else None

    db_size_bytes = get_db_size(conn)

    opp_count = conn.execute(
        "SELECT COUNT(*) FROM opportunities WHERE timestamp >= datetime('now', '-1 hour')"
    ).fetchone()[0]

    return {
        "status": "running",
        "last_update": last_update,
        "ticker_count": ticker_count,
        "opportunity_count": opp_count,
        "db_size_bytes": db_size_bytes,
        "polling_interval": POLLING_INTERVAL,
        "target_coins": TARGET_COINS,
    }


# --- SSE endpoint ---

@router.get("/stream")
async def stream(request: Request):
    """Server-Sent Events stream for real-time updates."""

    async def event_generator():
        conn = request.app.state.db
        prev_ticker_ts = None

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            try:
                # Check for new data
                row = conn.execute("SELECT MAX(timestamp) FROM tickers").fetchone()
                current_ts = row[0] if row else None

                if current_ts != prev_ticker_ts:
                    prev_ticker_ts = current_ts

                    # Send opportunities update
                    opps = get_latest_opportunities(conn, limit=20)
                    yield f"event: opportunities\ndata: {json.dumps({'opportunities': opps})}\n\n"

                    # Send spreads update
                    tickers = get_latest_tickers(conn)
                    spread_data = calc_spreads(tickers)
                    yield f"event: spreads\ndata: {json.dumps({'spreads': spread_data})}\n\n"

                    # Send status update
                    ticker_count = conn.execute("SELECT COUNT(*) FROM tickers").fetchone()[0]
                    opp_count = conn.execute(
                        "SELECT COUNT(*) FROM opportunities WHERE timestamp >= datetime('now', '-1 hour')"
                    ).fetchone()[0]
                    db_size = get_db_size(conn)

                    status_data = {
                        "status": "running",
                        "last_update": current_ts,
                        "ticker_count": ticker_count,
                        "opportunity_count": opp_count,
                        "db_size_bytes": db_size,
                        "polling_interval": POLLING_INTERVAL,
                        "target_coins": TARGET_COINS,
                    }
                    yield f"event: status\ndata: {json.dumps(status_data)}\n\n"

            except Exception:
                pass

            await asyncio.sleep(3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- What-If Simulator ---

class WhatIfRequest(BaseModel):
    amount_krw: float = Field(default=1_000_000, description="Investment amount in KRW")
    fee_override: float | None = Field(default=None, description="Override fee rate (e.g. 0.001)")
    slippage_pct: float = Field(default=0.1, description="Estimated slippage %")
    path: str | None = Field(default=None, description="Specific path to simulate (e.g. 'binance:BTC->upbit:BTC')")


@router.post("/whatif")
async def whatif(request: Request, body: WhatIfRequest):
    """What-If simulator: estimate profit for a given investment."""
    conn = request.app.state.db
    tickers = get_latest_tickers(conn)

    if not tickers:
        return {"error": "No ticker data available"}

    price_map = _build_price_map(tickers)
    implied_rate = calc_implied_rate(price_map)

    if implied_rate is None:
        return {"error": "Cannot calculate implied rate"}

    # Use override fee or defaults
    buy_fee = body.fee_override if body.fee_override is not None else BINANCE_FEE
    sell_fee = body.fee_override if body.fee_override is not None else UPBIT_FEE
    slippage = body.slippage_pct / 100.0

    # If a specific path is given, simulate it
    if body.path:
        return _simulate_path(body.path, body.amount_krw, buy_fee, sell_fee, slippage, price_map, implied_rate)

    # Otherwise, simulate all coins with default buy-on-Binance, sell-on-Upbit
    results = []
    spread_data = calc_spreads(tickers, implied_rate=implied_rate)

    for s in spread_data:
        symbol = s["symbol"]
        binance_ask = s["binance_ask"]
        upbit_bid = s["upbit_bid"]

        if not binance_ask or not upbit_bid or binance_ask <= 0:
            continue

        # 1. Convert KRW to USDT via implied rate
        usdt_amount = body.amount_krw / implied_rate

        # 2. Buy on Binance
        coins_bought = (usdt_amount / binance_ask) * (1 - buy_fee) * (1 - slippage)

        # 3. Transfer (withdrawal fee)
        withdrawal_fee = WITHDRAWAL_FEES.get(symbol, 0)
        coins_after_transfer = coins_bought - withdrawal_fee
        if coins_after_transfer <= 0:
            continue

        # 4. Sell on Upbit
        krw_received = coins_after_transfer * upbit_bid * (1 - sell_fee) * (1 - slippage)

        gross_profit = krw_received - body.amount_krw
        net_profit_pct = (krw_received / body.amount_krw - 1) * 100

        fee_total_krw = (
            usdt_amount * binance_ask * buy_fee * implied_rate +  # buy fee in KRW
            withdrawal_fee * upbit_bid +  # withdrawal fee in KRW
            coins_after_transfer * upbit_bid * sell_fee  # sell fee in KRW
        )

        results.append({
            "symbol": symbol,
            "amount_krw": body.amount_krw,
            "krw_received": round(krw_received),
            "gross_profit_krw": round(gross_profit),
            "net_profit_pct": round(net_profit_pct, 4),
            "fees_krw": round(fee_total_krw),
            "implied_rate": round(implied_rate, 2),
            "slippage_pct": body.slippage_pct,
        })

    results.sort(key=lambda x: x["net_profit_pct"], reverse=True)
    return {"simulations": results}


def _simulate_path(path_str, amount_krw, buy_fee, sell_fee, slippage, price_map, implied_rate):
    """Simulate a specific path."""
    steps = path_str.split("->")
    if len(steps) < 2:
        return {"error": "Path must have at least 2 nodes"}

    current_value = amount_krw
    fee_total = 0.0
    step_details = []

    for i in range(len(steps) - 1):
        src = steps[i]
        dst = steps[i + 1]
        src_ex, src_sym = src.split(":")
        dst_ex, dst_sym = dst.split(":")

        src_data = price_map.get((src_ex, src_sym))
        dst_data = price_map.get((dst_ex, dst_sym))

        if not src_data or not dst_data:
            return {"error": f"No data for {src} or {dst}"}

        if src_ex == dst_ex:
            # Intra-exchange trade
            bid = src_data["bid_price"]
            ask = dst_data["ask_price"]
            if not bid or not ask or ask <= 0:
                return {"error": f"Invalid prices for {src}->{dst}"}
            fee = buy_fee
            rate = (bid / ask) * (1 - fee) * (1 - slippage)
            fee_amount = current_value * fee
            fee_total += fee_amount
            current_value *= rate
        else:
            # Cross-exchange transfer
            withdrawal_fee = WITHDRAWAL_FEES.get(src_sym, 0)
            # Price of one coin in current currency
            coin_price = src_data["bid_price"]
            if coin_price > 0:
                coins = current_value / coin_price
                coins -= withdrawal_fee
                if coins <= 0:
                    return {"error": f"Withdrawal fee exceeds balance at {src}"}
                # Convert to destination currency
                dst_coin_price = dst_data["bid_price"]
                fee_amount = withdrawal_fee * coin_price
                fee_total += fee_amount
                current_value = coins * dst_coin_price * (1 - slippage)

        step_details.append({
            "from": src,
            "to": dst,
            "value_after": round(current_value),
        })

    return {
        "path": path_str,
        "amount_krw": amount_krw,
        "final_value": round(current_value),
        "gross_profit": round(current_value - amount_krw),
        "net_profit_pct": round((current_value / amount_krw - 1) * 100, 4),
        "total_fees": round(fee_total),
        "steps": step_details,
    }
