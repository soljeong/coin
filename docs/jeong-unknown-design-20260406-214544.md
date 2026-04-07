# 설계: 크로스 거래소 아비트리지 모니터 (업비트 x 바이낸스)

/office-hours로 생성 — 2026-04-06
Branch: unknown
Repo: coin
Status: APPROVED
Mode: Builder

## 문제 정의

업비트(KRW 마켓)와 바이낸스(USDT 마켓) 간 가격 차이를 모니터링하고, 그래프 기반 경로 탐색으로 아비트리지 기회를 탐지하며, 실시간 웹 대시보드로 시각화하는 시스템. 거래소 API, 그래프 알고리즘, 비용 모델링, 실시간 데이터 시각화를 배우기 위한 학습 프로젝트.

## 이 프로젝트가 흥미로운 이유

그래프 기반 경로 탐색 접근법. 대부분의 아비트리지 도구는 단순 A-B 스프레드 비교를 한다. 거래소-코인 쌍을 그래프 노드로, 거래/전송을 가중치 간선으로 모델링하고 수익성 있는 사이클을 찾는 것은 정말 우아한 수학적 추상화다. 단순 스프레드, 삼각 아비트리지, 크로스 거래소 다단계 경로를 하나의 알고리즘으로 통합할 수 있다.

브릿지 코인 인사이트도 재미있는 부분: 외환 API 대신 실제 XRP/XLM 전송 가격을 암묵적 KRW-USDT 환율로 사용. 이것이 실제로 아비트리저들이 크로스보더 크립토 흐름을 생각하는 방식이다.

## 제약 조건

- **업비트**: Private API 키 보유 (KRW 마켓)
- **바이낸스**: Public API만 사용 (USDT 마켓)
- **거래 실행 없음** — 이 단계에서는 모니터링/분석만
- **로컬 배포** (localhost, 단일 사용자)
- **Python** 생태계 (FastAPI, ccxt, sqlite3)
- 예산: 0원 (유료 API 없음, 클라우드 호스팅 없음)

## 전제 조건

1. **3초 간격 REST 폴링이면 충분하다.** 김치 프리미엄은 구조적(한국 자본 규제)이며 수시간~수일 지속된다. 밀리초 단위 레이턴시는 거래소 내 HFT 아비트리지에나 필요하다.
2. **그래프 기반 경로 탐색이 올바른 추상화다.** 2개 거래소, ~100개 공통 코인에 대한 다단계 아비트리지 분석에 적합.
3. **SQLite로 충분하다.** 3초마다 ~200개 행 (100 코인 x 2 거래소) 저장은 SQLite 한계 내.
4. **브릿지 코인 가격 > 외환 API.** 실제 전송 가격이 공식 환율보다 크립토 시장 현실을 더 정확히 반영.
5. **모니터링 전용이 유효한 첫 단계다.** 실제 돈의 리스크 없이 핵심 학습 가치를 제공.

## 크로스 모델 관점

Claude 서브에이전트가 독립적으로 설계를 리뷰했다:

1. **아직 고려하지 않은 가장 멋진 버전:** "김치 프리미엄 서피스" — 3D 히트맵 (코인 x 시간 x 수익) + "What-If" 시뮬레이터. 슬라이더로 환율, 수수료, 전송 시간을 조정하면 지형이 실시간으로 변한다. 모니터를 추론 도구로 전환.

2. **빌더가 가장 흥미로워하는 것:** 그래프 기반 경로 탐색. "단순히 스프레드를 보고 싶은 사람은 그래프 이론을 추상화로 선택하지 않는다. 이 사람은 시장 아래의 수학적 구조에 흥미를 느끼는 것이다."

3. **50% 지름길:** [ccxt](https://github.com/ccxt/ccxt) — 통합 암호화폐 거래소 API (업비트, 바이낸스 포함 100개+ 거래소 지원). Collector 레이어 전체를 대체. 직접 만들어야 할 것: 그래프 엔진, 브릿지 코인 가격 계산, 저장소, 분석, 대시보드.

4. **주말 빌드 순서:** 10개 코인 + 브릿지 스프레드 계산기 (토요일) → Chart.js 대시보드 (토요일 저녁) → 100개 코인 확장 (일요일). 그래프 엔진은 데이터 감각을 기른 후 2주차에.

## 검토한 접근법

### 접근법 A: 스프레드 대시보드 우선 (최소 구현)
그래프 엔진 전에 브릿지 코인 스프레드 계산기와 대시보드를 먼저 구축. ccxt로 데이터 수집. 10개 코인으로 시작, 100개로 확장.
- 노력: S (주말)
- 리스크: 낮음
- 장점: 즉각적인 피드백, 데이터 감각 우선
- 단점: 그래프 엔진(재미있는 부분) 지연, 단순한 분석
- 완성도: 6/10

### 접근법 B: 그래프 엔진 우선 (원본 스펙)
원본 스펙 그대로 진행. 커스텀 수집기(httpx), 4개 레이어 전부, 첫날부터 100개 코인.
- 노력: M (1-2주)
- 리스크: 중간
- 장점: 그래프 알고리즘 깊이 학습, 만족스러운 아키텍처
- 단점: 첫 결과물까지 오래 걸림, 커스텀 수집기는 삽질
- 완성도: 8/10

### 접근법 C: 하이브리드 — ccxt + 그래프 엔진 (선택됨)
데이터 수집은 ccxt로 (커스텀 수집기 생략), 분석은 바로 그래프 엔진으로. What-If 시뮬레이터는 스트레치 목표.
- 노력: M (1주)
- 리스크: 낮음-중간
- 장점: 지적으로 흥미로운 작업에 가장 빠른 경로, API 배관 작업 생략
- 단점: 거래소 API 내부에 대한 학습 감소
- 완성도: 9/10

## 추천 접근법

**접근법 C: 하이브리드 (ccxt + 그래프 엔진)**. ccxt로 업비트/바이낸스 데이터 수집을 정규화. 엔지니어링 에너지를 그래프 기반 경로 탐색, 비용 모델링, 대시보드 시각화에 집중. 세컨드 오피니언의 What-If 시뮬레이터는 적은 노력으로 높은 임팩트.

### 수정된 아키텍처

```
[ccxt Collector]          [Storage]         [Analysis]          [Dashboard]

 ccxt.upbit    ──┐                                          
                 ├──▶  SQLite DB  ──▶  Graph Engine  ──▶  FastAPI +
 ccxt.binance  ──┘                     (pathfinder)       HTML/JS/Chart.js
                                                          + What-If Sim
                                                          (localhost)
```

### 수정된 프로젝트 구조

```
coin/
├── config/
│   ├── settings.py          # API 키, 수수료율, 임계값
│   └── .env                 # 시크릿 (gitignore)
├── collectors/
│   └── exchange.py          # ccxt 기반 통합 수집기
├── analysis/
│   ├── graph.py             # 거래소-코인 그래프 구성
│   ├── pathfinder.py        # 수익성 사이클 탐지
│   └── cost.py              # 수수료/슬리피지 계산
├── storage/
│   └── db.py                # SQLite 스키마 및 접근 레이어
├── dashboard/
│   ├── app.py               # FastAPI 서버
│   ├── api.py               # REST endpoints + SSE
│   └── static/
│       ├── index.html        # 메인 대시보드
│       ├── app.js            # Chart.js + 실시간 업데이트
│       └── style.css         # 다크 터미널 테마
├── main.py                  # 진입점 (asyncio)
├── requirements.txt
└── README.md
```

### 핵심 의존성

- `ccxt` — 통합 거래소 API (httpx + pyupbit 대체)
- `fastapi` + `uvicorn` — 대시보드 서버
- `sqlite3` — 내장 스토리지
- `chart.js` (CDN) — 프론트엔드 차트

### 빌드 순서

0. **Day 0 (진행/중단 게이트): 완료 ✓**
   - 결과: **GO** (188개 공통 코인, Day 1 대상 9/10 확인)
   - **발견된 이슈:** ccxt `fetch_tickers()`와 `fetch_ticker()`가 업비트에서 `bid=None, ask=None` 반환. `last`(체결가)만 제공됨.
   - **해결책:** 업비트는 `fetch_order_books(symbols, limit=1)`로 bid/ask 수집. 바이낸스는 `fetch_tickers()` 정상 사용.
   - **수집기 전략 변경:** 거래소별 다른 API 호출 방식 필요:
     - 업비트: `fetch_order_books()` → bid/ask + `fetch_tickers()` → last, volume
     - 바이낸스: `fetch_tickers()` → bid/ask/last/volume 전부 제공
   - **MATIC 누락:** 폴리곤이 POL로 리브랜딩됨. Day 1 대상에서 MATIC → POL로 대체.
1. **Day 1:** ccxt 수집기 → SQLite 저장. 10개 고거래량 코인으로 시작 (BTC, ETH, XRP, SOL, ADA, DOGE, LINK, DOT, AVAX, POL). DB 저장 확인.
2. **Day 2:** 브릿지 코인 스프레드 계산기. XRP 가격으로 암묵적 KRW/USDT 환율 산출. 수수료 차감 후 순 스프레드 계산. 전체 코인으로 확장.
3. **Day 3:** 그래프 엔진. 거래소-코인 그래프 구축, 사이클 탐지 구현 (최대 4-5 홉), 간선 가중치 `w = -log(effective_rate * (1 - fee))`로 벨만-포드 음수 사이클 탐지.
4. **Day 4:** FastAPI 대시보드. 기회 테이블 (수익률 순 정렬), 김치 프리미엄 히트맵, 브릿지 스프레드 차트.
5. **Day 5:** SSE 실시간 업데이트. What-If 시뮬레이터 (스트레치). 이력/통계 페이지.

### 그래프 용어 정의

- **노드:** 거래소-코인 쌍 (예: 업비트-BTC, 바이낸스-ETH). 총 ~200개 노드.
- **간선:** 거래 (같은 거래소에서 A를 B로 매매, 비용 = 거래 수수료) 또는 크로스 거래소 전송 (코인 C를 거래소 X에서 Y로 이동, 비용 = 출금 수수료 + 전송 지연으로 인한 추정 슬리피지).
- **홉:** 단일 간선 순회. 3홉 경로 예시: 바이낸스에서 XRP 매수 → XRP를 업비트로 전송 → 업비트에서 XRP를 KRW로 매도.
- **간선 가중치:** `w = -log(effective_rate * (1 - fee))`. 수익성 있는 사이클은 총 가중치가 음수 (벨만-포드가 이를 탐지).

### 데이터 스키마

```sql
CREATE TABLE tickers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,        -- 'upbit' 또는 'binance'
    symbol TEXT NOT NULL,          -- 'BTC', 'ETH' 등
    bid_price REAL NOT NULL,       -- 최고 매수호가 (이 가격에 팔 수 있음)
    ask_price REAL NOT NULL,       -- 최저 매도호가 (이 가격에 살 수 있음)
    volume_24h REAL,
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,            -- JSON: ["binance:BTC","upbit:XRP",...]
    hops INTEGER NOT NULL,
    gross_spread REAL NOT NULL,    -- 수수료 전 (%)
    net_profit REAL NOT NULL,      -- 모든 비용 차감 후 (%)
    total_fees REAL NOT NULL,      -- 총 수수료 (%)
    risk_level TEXT NOT NULL,      -- 'LOW', 'MED', 'HIGH'
    timestamp DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 빠른 조회를 위한 인덱스
CREATE INDEX idx_tickers_ts ON tickers(timestamp DESC);
CREATE INDEX idx_tickers_exchange_symbol ON tickers(exchange, symbol);
CREATE INDEX idx_opportunities_profit ON opportunities(net_profit DESC);
```

**데이터 보존 정책:** 티커 이력 7일, 기회 이력 30일 보관. 시작 시 및 매 24시간마다 정리 작업 실행: `DELETE FROM tickers WHERE timestamp < datetime('now', '-7 days')`.

### 장애 대응

- **API 다운타임:** `fetch_tickers()` 예외 발생 시 10초 후 재시도 (최대 3회, 이후 60초 대기). 마지막 성공 조회가 15초 이상 경과하면 대시보드에 "DATA STALE" 표시.
- **레이트 리밋:** 업비트는 ~10 req/s 허용. `fetch_order_books()`는 심볼 목록을 받아 한 번에 처리하므로 3초당 1-2회 요청은 한계 내. 바이낸스는 1200 req/min, `fetch_tickers()`는 단일 요청. 배칭 불필요.
- **부분 데이터:** 한 거래소만 데이터를 반환하면 모든 크로스 거래소 기회를 "STALE"로 표시하고 거래소 내 데이터만 표시.
- **네트워크 문제:** ccxt가 내부적으로 재연결 처리. 5분 이상 지속 실패 시 콘솔에 경고 로그.

## 미해결 질문

1. ~~**ccxt 업비트 지원 품질:**~~ **해결됨 (Day 0):** `fetch_tickers()`는 bid/ask를 반환하지 않음. `fetch_order_books(symbols, limit=1)`로 대체. 바이낸스는 정상.
2. ~~**그래프 알고리즘 선택:**~~ **해결됨:** `w = -log(effective_rate * (1 - fee))`를 사용한 벨만-포드. DFS 가지치기는 더 큰 그래프에서 성능 문제가 있을 경우 향후 최적화 옵션.
3. **What-If 시뮬레이터 범위:** 비용 모델의 어느 부분까지 조정 가능하게 할 것인가? 수수료와 전송 시간만? 슬리피지 추정도?
4. ~~**데이터 보존 정책:**~~ **해결됨:** 티커 7일, 기회 30일. 매일 시작 시 정리 작업 실행.

## 성공 기준

- 데이터 신선도 5초 이내의 실시간 대시보드에서 아비트리지 기회 표시
- 그래프 엔진이 다단계 수익성 사이클을 정확히 식별
- 브릿지 코인 스프레드 계산이 수동 계산 대비 0.01% 이내
- What-If 시뮬레이터가 슬라이더 변경 시 히트맵/테이블 업데이트
- 크래시나 메모리 누수 없이 24시간 연속 실행 가능
- 학습 목표 달성: 비동기 Python, 그래프 알고리즘, 거래소 API, 실시간 웹 대시보드

## 배포 계획

현재는 로컬 전용. `python main.py`로 수집기와 대시보드를 localhost에서 시작. 배포 파이프라인 불필요. 추후 공유 시 Dockerfile이 자연스러운 배포 방법.

## 다음 단계

1. ~~`pip install ccxt fastapi uvicorn` 후 ccxt 검증~~ **완료 (Day 0)**
2. 수집기 구축 및 SQLite로 데이터 흐름 확인 (업비트: `fetch_order_books`, 바이낸스: `fetch_tickers`)
3. 사이클 탐지를 포함한 그래프 엔진 구현
4. 대시보드 연결 (와이어프레임 참조: `docs/wireframe-dashboard.html`)
5. What-If 시뮬레이터 추가

## 당신의 사고방식에서 주목한 것

- 코드 한 줄 작성하기 전에 4개 레이어 아키텍처 스펙을 데이터 스키마, 프로젝트 구조, 의존성 목록까지 포함하여 완성했다. 그건 단순한 열정이 아니라 엔지니어링 규율이다.
- 브릿지 코인 인사이트 — 외환 API 대신 실제 전송 가격을 암묵적 환율로 사용 — 교과서에 나온 설명이 아니라 크립토 시장이 실제로 어떻게 작동하는지 이해하고 있다는 증거다.
- 단순 스프레드 비교가 "명백한" 접근법일 때 그래프 기반 사이클 탐지를 선택했다. 결과가 아니라 수학에 관심이 있기 때문에 더 어렵고 우아한 추상화를 골랐다.
- "모니터링/분석 단계로 시작하며, 실제 거래 실행은 향후 확장" — 실행 전에 모니터링을 먼저 시작하는 것은 절제력이다. 대부분의 사람들은 트레이딩 봇으로 바로 뛰어들고 싶어한다. 당신은 데이터를 먼저 이해하고 싶어한다.
