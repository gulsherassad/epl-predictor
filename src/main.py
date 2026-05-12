from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import router

app = FastAPI(title="EPL Predictor", version="1.0.0")

_BASE = Path(__file__).resolve().parent.parent
_FRONTEND = _BASE / "frontend"

app.mount("/static", StaticFiles(directory=str(_FRONTEND)), name="static")

app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def home():
    return (_FRONTEND / "index.html").read_text(encoding="utf-8")


@app.get("/fixtures-page", response_class=HTMLResponse)
async def fixtures_page():
    return (_FRONTEND / "fixtures.html").read_text(encoding="utf-8")
