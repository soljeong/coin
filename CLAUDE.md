# CLAUDE.md

## gstack

Use the `/browse` skill from gstack for all web browsing. Never use `mcp__claude-in-chrome__*` tools.

### Available gstack skills

- `/office-hours` - Office hours
- `/plan-ceo-review` - CEO review planning
- `/plan-eng-review` - Engineering review planning
- `/plan-design-review` - Design review planning
- `/design-consultation` - Design consultation
- `/design-shotgun` - Design shotgun
- `/design-html` - Design HTML
- `/review` - Code review
- `/ship` - Ship code
- `/land-and-deploy` - Land and deploy
- `/canary` - Canary deployment
- `/benchmark` - Benchmarking
- `/browse` - Web browsing (use this for ALL web browsing)
- `/connect-chrome` - Connect to Chrome
- `/qa` - Quality assurance
- `/qa-only` - QA only
- `/design-review` - Design review
- `/setup-browser-cookies` - Setup browser cookies
- `/setup-deploy` - Setup deployment
- `/retro` - Retrospective
- `/investigate` - Investigation
- `/document-release` - Document release
- `/codex` - Codex
- `/cso` - CSO
- `/autoplan` - Auto planning
- `/plan-devex-review` - DevEx review planning
- `/devex-review` - DevEx review
- `/careful` - Careful mode
- `/freeze` - Freeze
- `/guard` - Guard
- `/unfreeze` - Unfreeze
- `/gstack-upgrade` - Upgrade gstack
- `/learn` - Learn

## 프로젝트 개요

크로스 거래소 아비트리지 모니터링 시스템 (업비트 KRW x 바이낸스 USDT).
설계 문서: `~/.gstack/projects/coin/jeong-unknown-design-20260406-214544.md`

### 기술 스택

- Python 3, venv (`venv/`)
- ccxt (거래소 API), FastAPI + uvicorn (대시보드), SQLite (저장소)
- Chart.js (프론트엔드 차트)

### 아키텍처

ccxt Collector → SQLite → Graph Engine (벨만-포드) → FastAPI 대시보드

### Day 0 검증 결과 (2026-04-06)

- **업비트 ccxt 주의사항:** `fetch_tickers()`, `fetch_ticker()`는 `bid=None, ask=None` 반환. `last`만 제공됨. 반드시 `fetch_order_books(symbols, limit=1)`로 bid/ask 수집할 것.
- **바이낸스:** `fetch_tickers()` 정상 (bid/ask/last/volume 전부 제공)
- **공통 코인:** 188개. Day 1 대상 10개: BTC, ETH, XRP, SOL, ADA, DOGE, LINK, DOT, AVAX, POL
- **MATIC → POL:** 폴리곤 리브랜딩으로 MATIC이 공통 코인에 없음. POL로 대체.

### 수집기 전략 (거래소별 다름)

```
업비트:  fetch_order_books(symbols, limit=1) → bid/ask
         fetch_tickers() → last, volume_24h
바이낸스: fetch_tickers() → bid/ask/last/volume 전부
```

### 빌드 진행 상황

- [x] Day 0: ccxt 검증 게이트 (GO)
- [x] Day 1: 수집기 + SQLite 저장 (branch: feat/day1-collector-storage)
- [x] Day 2: 브릿지 코인 스프레드 계산기 (branch: feat/day1-collector-storage)
- [ ] Day 3: 그래프 엔진 (벨만-포드 사이클 탐지)
- [ ] Day 4: FastAPI 대시보드
- [ ] Day 5: SSE 실시간 + What-If 시뮬레이터

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
