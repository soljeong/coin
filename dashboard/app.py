"""FastAPI application for the arbitrage monitor dashboard."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from dashboard.api import router
from storage.db import init_db
from config.settings import DB_PATH


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB connection on startup."""
    conn = init_db(DB_PATH)
    # Enable WAL mode for concurrent reads
    conn.execute("PRAGMA journal_mode=WAL")
    app.state.db = conn
    yield
    conn.close()


app = FastAPI(title="Arbitrage Monitor", lifespan=lifespan)
app.include_router(router, prefix="/api")

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
