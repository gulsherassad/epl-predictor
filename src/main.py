from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.api.routes import router

app = FastAPI(title="EPL Predictor", version="1.0.0")

_BASE = Path(__file__).resolve().parent.parent
_FRONTEND = _BASE / "frontend"

app.mount("/static", StaticFiles(directory=str(_FRONTEND)), name="static")
_templates = Jinja2Templates(directory=str(_FRONTEND))

app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return _templates.TemplateResponse("index.html", {"request": request})


@app.get("/fixtures-page", response_class=HTMLResponse)
async def fixtures_page(request: Request):
    return _templates.TemplateResponse("fixtures.html", {"request": request})
