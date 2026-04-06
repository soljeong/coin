# Design System — Arbitrage Monitor (아비트리지 모니터)

## Product Context
- **What this is:** 업비트(KRW) x 바이낸스(USDT) 크로스 거래소 아비트리지 모니터링 대시보드
- **Who it's for:** 크립토에 관심 있는 개발자/트레이더 (단일 사용자, 로컬)
- **Space/industry:** 크립토 아비트리지/트레이딩 인텔리전스 도구
- **Project type:** 데이터 중심 웹 대시보드 (FastAPI + Chart.js)

## Aesthetic Direction
- **Direction:** Industrial/Utilitarian
- **Decoration level:** Minimal
- **Mood:** 데이터가 주인공인 프로급 트레이딩 인텔리전스 도구. Bloomberg Terminal의 정보 밀도에 현대적 가독성을 더한 느낌. "이걸로 시장을 읽을 수 있겠다."
- **Reference sites:** TradingView, Aurox, Arbitra (Dribbble)

## Typography
- **Display/Hero:** Geist — 깔끔한 기하학적 산세리프. 모던하면서 과하지 않음.
- **Body:** Geist — 같은 패밀리로 통일. 시각적 잡음 최소화.
- **UI/Labels:** Geist (same as body)
- **Data/Tables:** Geist Mono — tabular-nums 지원, 숫자 정렬 완벽. 가격/수익률 표시에 필수.
- **Code:** JetBrains Mono
- **Loading:** Google Fonts CDN (`https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap`)
- **Scale:**
  - 3xl: 30px / 1.875rem (페이지 타이틀)
  - 2xl: 24px / 1.5rem (섹션 헤더)
  - xl: 20px / 1.25rem (카드 타이틀)
  - lg: 16px / 1rem (본문)
  - md: 14px / 0.875rem (테이블 데이터, UI 라벨)
  - sm: 12px / 0.75rem (캡션, 타임스탬프)
  - xs: 10px / 0.625rem (배지, 미세 라벨)

## Color
- **Approach:** Restrained + Semantic
- **Primary accent:** #F0B90B (amber/gold) — 기회 발견, CTA, 활성 상태. 어둠 속 신호등.
- **Secondary:** #1E90FF (blue) — 중립 데이터, 링크, 정보성 요소.
- **Background:** #0B0E11 (near-black) — 메인 배경
- **Surface:** #1E2329 — elevated 카드, 패널
- **Surface hover:** #252A31 — 카드/행 호버 상태
- **Border:** #2B3139 — 카드 테두리, 구분선
- **Text primary:** #EAECEF — 메인 텍스트
- **Text secondary:** #B7BDC6 — 보조 텍스트
- **Text muted:** #848E9C — 비활성, 타임스탬프
- **Semantic:**
  - Profit/Success: #0ECB81 (green)
  - Loss/Error: #F6465D (red)
  - Warning: #FCD535 (yellow)
  - Info: #1E90FF (blue)
- **Dark mode:** 기본이 다크 모드. 라이트 모드 미지원 (트레이딩 도구 특성).

## Spacing
- **Base unit:** 4px
- **Density:** Compact (데이터 밀도 우선)
- **Scale:**
  - 2xs: 2px
  - xs: 4px
  - sm: 8px
  - md: 12px
  - lg: 16px
  - xl: 24px
  - 2xl: 32px
  - 3xl: 48px

## Layout
- **Approach:** Grid-disciplined
- **Grid:** 12 columns (desktop), 6 columns (tablet), 1 column (mobile)
- **Max content width:** 1440px
- **Sidebar:** 240px (고정), 아이콘 모드 64px
- **Border radius:**
  - sm: 4px (버튼, 입력 필드, 배지)
  - md: 8px (카드, 패널)
  - lg: 12px (모달, 대형 컨테이너)
  - full: 9999px (아바타, 상태 인디케이터)

## Motion
- **Approach:** Minimal-functional
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:**
  - micro: 50ms (가격 변동 flash)
  - short: 150ms (호버 상태, 토글)
  - medium: 250ms (카드 진입, 패널 열기)
  - long: 400ms (페이지 전환)
- **실시간 데이터 패턴:**
  - 가격 상승: 배경 #0ECB81 10% opacity flash → fade out (micro)
  - 가격 하락: 배경 #F6465D 10% opacity flash → fade out (micro)
  - 새 기회 진입: 행 slide-in from top (medium)
  - 기회 소멸: 행 fade-out (short)

## Component Patterns
- **테이블:** 컴팩트 행 높이 (36px), 호버 시 Surface hover, 헤더 고정
- **카드:** Surface 배경 + Border, 내부 패딩 md(12px), 카드 간 간격 sm(8px)
- **수익률 표시:** Geist Mono, Profit/Loss 색상 적용, % 기호 포함
- **히트맵:** Profit(green) → neutral(gray) → Loss(red) 그라데이션
- **그래프 시각화:** 노드는 원형(거래소별 색상), 엣지는 수익률에 따라 두께/색상 변화

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-06 | 디자인 시스템 생성 | /design-consultation 기반. 리서치: TradingView, Aurox, Arbitra 등 트레이딩 대시보드 분석 |
| 2026-04-06 | Amber/gold 악센트 채택 | 블루 대신 amber로 '기회 발견' 신호. 크로스 거래소 인텔리전스 도구의 차별점 |
| 2026-04-06 | Geist 패밀리 올인 | Inter/Roboto 대비 덜 뻔하면서 가독성 우수. Mono 변형으로 데이터 표시 통일 |
| 2026-04-06 | 다크 모드 전용 | 트레이딩 도구 특성상 장시간 사용. 라이트 모드 불필요 |
| 2026-04-06 | Compact 스페이싱 | 한 화면에 최대한 많은 데이터 표시. 트레이딩 터미널 접근법 |
