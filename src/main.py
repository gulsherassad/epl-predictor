import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src import analytics
from src.api.routes import router

logger = logging.getLogger(__name__)

_DATA_STALE_DAYS = 7


async def _auto_refresh() -> None:
    """Background task: fetch latest season results and reload the model state."""
    from src.data.updater import current_season, fetch_season_csv, rebuild_parquet
    from src.api.routes import get_state

    loop = asyncio.get_event_loop()
    try:
        season = current_season()
        logger.info("Auto-refresh: fetching season %s/%s …", season, season + 1)
        await loop.run_in_executor(None, fetch_season_csv, season)
        await loop.run_in_executor(None, rebuild_parquet)
        if hasattr(get_state, "_cache"):
            del get_state._cache
        from src.api.routes import _PREDICT_CACHE
        _PREDICT_CACHE.clear()
        logger.info("Auto-refresh complete.")
    except Exception as exc:
        logger.warning("Auto-refresh failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    analytics.init()

    from src.api.routes import get_state

    # Pre-warm the model so the first real request is fast
    loop = asyncio.get_event_loop()
    try:
        logger.info("Pre-warming model state…")
        await loop.run_in_executor(None, get_state)
        logger.info("Model state ready.")
    except Exception as exc:
        logger.warning("Model pre-warm failed: %s", exc)

    # Pre-warm the fixtures cache in the background so the fixtures page loads instantly
    async def _warm_fixtures():
        from src.api.routes import fixtures as fetch_fixtures
        try:
            logger.info("Pre-warming fixtures cache…")
            await loop.run_in_executor(None, fetch_fixtures)
            logger.info("Fixtures cache ready.")
        except Exception as exc:
            logger.warning("Fixtures pre-warm failed: %s", exc)

    asyncio.create_task(_warm_fixtures())

    # Trigger a background data refresh if training data is stale
    parquet = Path(__file__).resolve().parents[1] / "data" / "processed" / "matches.parquet"
    if parquet.exists():
        df = pd.read_parquet(parquet, columns=["Date"])
        latest = pd.to_datetime(df["Date"]).max()
        latest_utc = latest.to_pydatetime().replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - latest_utc).days
        if age_days >= _DATA_STALE_DAYS:
            logger.info("Training data is %d days old — scheduling background refresh.", age_days)
            asyncio.create_task(_auto_refresh())

    yield


app = FastAPI(title="EPL Predictor", version="1.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)

_BASE = Path(__file__).resolve().parent.parent
_FRONTEND = _BASE / "frontend"

app.mount("/static", StaticFiles(directory=str(_FRONTEND)), name="static")
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def home():
    from src.api.routes import get_state
    html = (_FRONTEND / "index.html").read_text(encoding="utf-8")
    try:
        from src.api.routes import _CURRENT_SEASON_TEAMS
        teams = sorted(set(get_state()["teams"]) | set(_CURRENT_SEASON_TEAMS))
        snippet = f"<script>window.TEAMS={json.dumps(teams)};</script>"
        html = html.replace("</head>", f"{snippet}</head>", 1)
    except Exception:
        pass
    return html


@app.get("/fixtures-page", response_class=HTMLResponse)
async def fixtures_page():
    return (_FRONTEND / "fixtures.html").read_text(encoding="utf-8")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    return (_FRONTEND / "dashboard.html").read_text(encoding="utf-8")
