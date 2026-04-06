# Coin Arbitrage Monitor

업비트(KRW) x 바이낸스(USDT) 크로스 거래소 아비트리지 모니터링 시스템.

브릿지 코인(XRP, XLM)을 이용해 내재 KRW/USDT 환율을 계산하고, 10개 대상 코인의 김치 프리미엄 및 순 스프레드를 실시간 추적합니다.

## 모니터링 대상 코인

BTC, ETH, XRP, SOL, ADA, DOGE, LINK, DOT, AVAX, POL

## 아키텍처

```
ccxt Collector → SQLite → Spread Engine → (FastAPI 대시보드 예정)
```

- **Collector**: 업비트는 `fetch_order_books` + `fetch_tickers`, 바이낸스는 `fetch_tickers`로 수집
- **Storage**: SQLite (`data/arbitrage.db`) — tickers, opportunities 테이블
- **Analysis**: 브릿지 코인 기반 내재 환율 계산, 김치 프리미엄 및 순 스프레드 산출

## 요구사항

- Python 3.10+
- 인터넷 연결 (거래소 API 접근)

## 설치

```bash
# 저장소 클론
git clone <repo-url>
cd coin

# 가상환경 생성 및 활성화
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

## 서버 실행

```bash
# 가상환경 활성화 후
python main.py
```

3초 간격으로 업비트/바이낸스에서 시세를 수집하고, 스프레드를 계산하여 로그로 출력합니다.

종료하려면 `Ctrl+C`를 누르세요.

### 실행 로그 예시

```
2026-04-06 22:00:00 [INFO] Initializing database at data/arbitrage.db
2026-04-06 22:00:01 [INFO] Collected 20 tickers (binance=10, upbit=10)
2026-04-06 22:00:01 [INFO] Top spread: BTC gross=3.42% net=2.87% (rate=1385 KRW/USDT)
```

## 설정

`config/settings.py`에서 주요 설정을 변경할 수 있습니다:

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `POLLING_INTERVAL` | 3초 | 수집 주기 |
| `UPBIT_FEE` | 0.05% | 업비트 거래 수수료 |
| `BINANCE_FEE` | 0.10% | 바이낸스 거래 수수료 |
| `DATA_STALE_THRESHOLD` | 15초 | 데이터 신선도 임계값 |
| `RETENTION_DAYS_TICKERS` | 7일 | 시세 데이터 보관 기간 |
| `RETENTION_DAYS_OPPORTUNITIES` | 30일 | 기회 데이터 보관 기간 |

## 테스트

```bash
pytest
```

## 프로젝트 구조

```
coin/
├── main.py                 # 진입점 (폴링 루프)
├── config/
│   └── settings.py         # 설정값
├── collectors/
│   └── exchange.py         # ccxt 기반 거래소 수집기
├── storage/
│   └── db.py               # SQLite 스키마 및 CRUD
├── analysis/
│   └── spread.py           # 브릿지 코인 환율 & 스프레드 계산
├── tests/                  # 테스트 스위트
├── data/                   # SQLite DB 파일
└── requirements.txt
```

## 로드맵

- [x] Day 0: ccxt 검증
- [x] Day 1: 수집기 + SQLite 저장
- [x] Day 2: 브릿지 코인 스프레드 계산기
- [ ] Day 3: 그래프 엔진 (벨만-포드 사이클 탐지)
- [ ] Day 4: FastAPI 대시보드
- [ ] Day 5: SSE 실시간 + What-If 시뮬레이터
