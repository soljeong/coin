# TODOS

## P2: 텔레그램/디스코드 알림
수익률 임계값 초과 시 텔레그램 봇 알림. python-telegram-bot ~50줄.
- **Why:** 대시보드를 계속 쳐다보지 않아도 기회 포착.
- **Effort:** S (human: ~2h / CC: ~10min)
- **Depends on:** Day 5 완료 (SSE + What-If)
- **Source:** CEO Review 2026-04-06, 확장 제안 1

## P2: 백테스트 모드
과거 시점의 그래프 엔진 돌려보기. What-If 시뮬레이터와 결합하여 과거 데이터 기반 시나리오 검증.
- **Why:** 시장 감각 + 전략 검증. 데이터 축적 후 의미 있음.
- **Effort:** M (human: ~4h / CC: ~20min)
- **Depends on:** Day 5 완료 + 이력 데이터 며칠 축적
- **Source:** CEO Review 2026-04-06, 확장 제안 6

## P3: What-If/히스토리 페이지 인터랙션 상태 정의
What-If 시뮬레이터와 히스토리 분석 페이지의 로딩/빈 화면/에러 상태 정의. 메인 대시보드는 정의됨 (CEO Plan 참조).
- **Why:** 구현자가 "데이터 없음" 상태를 임의로 처리하는 걸 방지. 트레이딩 도구에서 빈 상태는 사용자 신뢰를 좌우.
- **Effort:** XS (human: ~30min / CC: ~3min)
- **Depends on:** Day 5 구현 시점
- **Source:** Design Review 2026-04-06, Pass 2
