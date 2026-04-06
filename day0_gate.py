"""Day 0 Go/No-Go Gate: ccxt가 업비트와 바이낸스 티커를 정상 반환하는지 확인"""
import ccxt

def test_exchange(name, exchange):
    print(f"\n{'='*50}")
    print(f"[{name}] fetch_tickers() 테스트...")
    try:
        tickers = exchange.fetch_tickers()
        symbols = list(tickers.keys())
        print(f"  총 {len(symbols)}개 마켓 조회 성공")

        # bid/ask 확인 (첫 3개)
        for sym in symbols[:3]:
            t = tickers[sym]
            print(f"  {sym}: bid={t.get('bid')} ask={t.get('ask')}")

        # bid/ask가 None이 아닌 항목 수
        valid = sum(1 for t in tickers.values() if t.get('bid') and t.get('ask'))
        print(f"  bid/ask 유효: {valid}/{len(symbols)}")
        return tickers
    except Exception as e:
        print(f"  FAIL: {e}")
        return None

# 업비트 (KRW 마켓)
upbit = ccxt.upbit()
upbit_tickers = test_exchange("Upbit", upbit)

# 바이낸스 (USDT 마켓)
binance = ccxt.binance()
binance_tickers = test_exchange("Binance", binance)

# 공통 코인 교집합
if upbit_tickers and binance_tickers:
    print(f"\n{'='*50}")
    print("[교집합 계산]")

    upbit_coins = set()
    for sym in upbit_tickers:
        if '/KRW' in sym:
            upbit_coins.add(sym.split('/')[0])

    binance_coins = set()
    for sym in binance_tickers:
        if '/USDT' in sym:
            binance_coins.add(sym.split('/')[0])

    common = upbit_coins & binance_coins
    print(f"  업비트 KRW 마켓: {len(upbit_coins)}개")
    print(f"  바이낸스 USDT 마켓: {len(binance_coins)}개")
    print(f"  공통 코인: {len(common)}개")
    print(f"  목록: {sorted(common)[:20]}{'...' if len(common) > 20 else ''}")

    # 10개 고거래량 코인 확인
    target = ['BTC', 'ETH', 'XRP', 'SOL', 'ADA', 'DOGE', 'LINK', 'DOT', 'AVAX', 'MATIC']
    found = [c for c in target if c in common]
    missing = [c for c in target if c not in common]
    print(f"\n  Day 1 대상 코인 ({len(found)}/10 확인): {found}")
    if missing:
        print(f"  누락: {missing}")

    print(f"\n{'='*50}")
    print("GATE: GO" if len(common) >= 10 else "GATE: NO-GO (공통 코인 부족)")
else:
    print(f"\n{'='*50}")
    print("GATE: NO-GO (거래소 API 호출 실패)")
