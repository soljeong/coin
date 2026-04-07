# Docker Compose Containerization Design

## Goal

Split the monolithic `main.py` (collector + dashboard in one process) into three independent containers: PostgreSQL, collector, dashboard.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  collector   │────▶│  PostgreSQL  │◀────│  dashboard   │
│  (python)    │     │  (postgres)  │     │  (FastAPI)   │
└─────────────┘     └──────────────┘     └─────────────┘
                      port 5432            port 8000
```

Three containers on a shared Docker network. No direct communication between collector and dashboard — both talk only to the database.

## Containers

| Service | Image | Role |
|---------|-------|------|
| `db` | `postgres:16-alpine` | Data storage, persisted via named volume |
| `collector` | Custom (Python) | Polls exchanges every 3s, writes tickers + opportunities to DB |
| `dashboard` | Custom (Python) | FastAPI server, reads DB, serves web UI + SSE stream |

## Changes Required

### 1. Database layer: SQLite → PostgreSQL

**File: `storage/db.py`**

- Replace `sqlite3` with `psycopg2`
- Change parameter binding: `?` → `%s`
- Replace `sqlite3.Row` / `row_factory` with `RealDictCursor`
- Replace `conn.executescript()` with individual `conn.execute()` + `conn.commit()`
- SQL dialect changes:
  - `AUTOINCREMENT` → `SERIAL`
  - `DATETIME DEFAULT CURRENT_TIMESTAMP` → `TIMESTAMP DEFAULT NOW()`
  - `datetime('now', '-1 hour')` → `NOW() - INTERVAL '1 hour'`
  - `datetime('now', ? || ' hours')` → `NOW() - INTERVAL '%s hours'`
- `init_db()` accepts `database_url: str` instead of file path
- `PRAGMA journal_mode=WAL` removed (PostgreSQL handles concurrency natively)

### 2. Configuration

**File: `config/settings.py`**

- Replace `DB_PATH = 'data/arbitrage.db'` with `DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://arb:arb@localhost:5432/arbitrage')`
- Keep all other settings unchanged

### 3. Collector entrypoint

**New file: `collectors/main.py`**

- Extract the polling loop from `main.py` into a standalone module
- No dashboard thread, just the collection loop
- Connects to PostgreSQL via `DATABASE_URL`

### 4. Dashboard entrypoint

**File: `dashboard/app.py`**

- Change `init_db(DB_PATH)` → `init_db(DATABASE_URL)` in lifespan
- Remove `PRAGMA journal_mode=WAL`
- Remove `os.path.getsize(DB_PATH)` for db_size (use `pg_database_size()` instead)

**File: `dashboard/api.py`**

- Update `status` endpoint: replace `os.path.getsize` with PostgreSQL `pg_database_size()` query
- No other changes needed (SSE polling logic stays the same)

### 5. Docker files

**`Dockerfile`** — Single image for both collector and dashboard:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "collectors.main"]
```

**`docker-compose.yml`**:

```yaml
services:
  db:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: arbitrage
      POSTGRES_USER: arb
      POSTGRES_PASSWORD: arb
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U arb -d arbitrage"]
      interval: 5s
      retries: 5

  collector:
    build: .
    command: python -m collectors.main
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://arb:arb@db:5432/arbitrage
    restart: unless-stopped

  dashboard:
    build: .
    command: uvicorn dashboard.app:app --host 0.0.0.0 --port 8000
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://arb:arb@db:5432/arbitrage
    restart: unless-stopped

volumes:
  pgdata:
```

### 6. Dependencies

**`requirements.txt`** — Add `psycopg2-binary>=2.9.0`

### 7. main.py

- Keep for local (non-Docker) development but update to use PostgreSQL
- Remove the dashboard thread; just run the collector loop
- Optionally add `--with-dashboard` flag for local dev convenience

## What stays the same

- All analysis logic (`analysis/spread.py`, `analysis/graph.py`)
- Exchange collector (`collectors/exchange.py`)
- Frontend static files (`dashboard/static/`)
- SSE polling mechanism (DB poll every 3s)
- All config values except DB connection

## Testing

- Update existing tests to use PostgreSQL test database or keep SQLite for unit tests via an adapter
- `docker compose up` should bring up the full stack with no manual setup
