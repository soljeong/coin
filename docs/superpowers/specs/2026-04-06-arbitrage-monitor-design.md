# 크로스 거래소 아비트리지 모니터링 시스템

## 개요

업비트와 Binance 간 아비트리지 기회를 자동으로 탐지하고 웹 대시보드로 시각화하는 모니터링 시스템. 모니터링/분석 단계로 시작하며, 실제 거래 실행은 향후 확장.

## 대상 거래소

- **업비트** (KRW 마켓) — Private API Key 보유
- **Binance** (USDT 마켓) — Public API만 (추후 Key 발급)

빗썸은 제외.

## 아키텍처

```
[Collector Layer]          [Storage]         [Analysis]          [Dashboard]

 Upbit Collector  ──┐                                          
                    ├──▶  SQLite DB  ──▶  Path Finder  ──▶  FastAPI +
 Binance Collector ──┘                                        웹 대시보드
                                                              (localhost)
```

### 4개 레이어

1. **Collector** — 거래소별 가격 수집기. REST Polling (3초 간격)
2. **Storage** — SQLite에 가격 이력 저장
3. **Analysis** — 그래프 기반 경로 탐색으로 아비트리지 기회 탐지
4. **Dashboard** — FastAPI + HTML/JS로 브라우저 시각화

## 데이터 수집 (Collector)

### 공통 상장 코인 자동 탐색

- 앱 시작 시 각 거래소의 마켓 목록 API를 호출
- 2개 거래소 모두에 상장된 코인의 교집합을 자동 계산
- 1시간마다 교집합 갱신

### 수집 주기

- 전체 코인 시세: 3초 간격 (REST Polling)
- 각 거래소의 ticker API는 전체 코인을 한 번에 조회 가능

### 수집 데이터

| 필드 | 설명 |
|---|---|
| symbol | 코인 심볼 (BTC, ETH 등) |
| exchange | 거래소명 |
| bid_price | 최고 매수호가 (이 가격에 팔 수 있음) |
| ask_price | 최저 매도호가 (이 가격에 살 수 있음) |
| volume_24h | 24시간 거래량 |
| timestamp | 수집 시각 |

### 거래소 간 가격 비교 방식

환율 API가 아닌 **코인 송금(브릿지 코인)** 기준으로 비교.

- 업비트 ↔ Binance 간 실제 송금에 사용할 브릿지 코인 (XRP, XLM, USDT-TRC20 등) 가격 차이가 실질 환율 역할
- 수익성 계산에 포함할 비용:
  - 거래 수수료 (매수/매도 각각)
  - 출금 수수료 (네트워크 수수료)
  - 전송 시간 동안의 가격 변동 리스크 (슬리피지 추정)

## 아비트리지 분석 (Analysis)

### 경로 기반 통합 탐색

단순 2점 차익, 삼각 아비트리지, 거래소 간 삼각 경로를 하나의 그래프 로직으로 통합 처리.

- **노드**: 각 거래소의 각 코인 (업비트-BTC, Binance-ETH, ...)
- **간선**: 거래소 내 거래 (매매 수수료) 또는 거래소 간 전송 (출금 수수료 + 전송 시간)
- **탐색**: 시작점에서 출발하여 다시 돌아오는 경로 중 수익이 나는 사이클을 탐지
- **경로 깊이 제한**: 최대 4~5단계 (현실적 실행 가능성)

### 수익성 판단

- 각 기회마다 예상 순수익률(%) 계산
- 거래수수료, 출금수수료 차감한 실질 수익만 표시
- 설정 가능한 최소 수익률 임계값 (기본: 0.3%)

### 필터링

- 24시간 거래량이 너무 낮은 코인 제외
- 호가 깊이(depth)가 얕으면 슬리피지 경고

## 웹 대시보드

### 기술 스택

- 백엔드: FastAPI (Python)
- 프론트엔드: HTML + JavaScript (프레임워크 없음)
- 실시간 업데이트: SSE 또는 WebSocket

### 화면 구성

#### 메인 대시보드
- **실시간 기회 테이블**: 탐지된 아비트리지 기회 목록 (수익률 순 정렬)
  - 경로, 예상 수익률, 관련 코인, 거래량, 경로 단계 수
- **김치 프리미엄 현황**: 주요 코인별 업비트 vs Binance 가격 차이율

#### 기회 상세
- 각 단계별 가격, 수수료, 예상 소요 시간
- 최근 해당 경로의 수익률 변화 차트

#### 이력/통계
- 과거 탐지된 기회의 빈도, 평균 수익률, 지속 시간
- 어떤 코인/경로에서 기회가 자주 발생하는지 패턴 분석

## 프로젝트 구조

```
coin/
├── config/
│   ├── settings.py          # 거래소 API 키, 수수료율, 임계값 등
│   └── .env                 # 시크릿 (gitignore)
├── collectors/
│   ├── base.py              # 거래소 공통 인터페이스
│   ├── upbit.py             # 업비트 수집기
│   └── binance.py           # Binance 수집기
├── analysis/
│   ├── graph.py             # 거래소/코인 그래프 구성
│   ├── pathfinder.py        # 수익 경로 탐색 (사이클 탐지)
│   └── cost.py              # 수수료/슬리피지 계산
├── storage/
│   └── db.py                # SQLite 스키마 및 접근 레이어
├── dashboard/
│   ├── app.py               # FastAPI 서버
│   ├── static/              # HTML, JS, CSS
│   └── api.py               # 대시보드용 REST endpoints
├── main.py                  # 앱 진입점
├── requirements.txt
└── README.md
```

### 핵심 의존성

- `httpx` — 비동기 HTTP 클라이언트 (거래소 API 호출)
- `fastapi` + `uvicorn` — 대시보드 서버
- `sqlite3` — 내장 DB (별도 설치 불필요)
- `pyupbit` — 업비트 API 래퍼 (선택)

## 향후 확장

- 실제 거래 실행 모듈 추가
- WebSocket 기반 실시간 수집으로 업그레이드
- 빗썸 등 추가 거래소 지원
- 텔레그램/디스코드 알림
