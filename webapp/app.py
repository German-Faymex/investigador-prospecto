"""Investigador de Prospectos - Web Application."""
import sys
from pathlib import Path

WEBAPP_DIR = Path(__file__).parent
PROJECT_ROOT = WEBAPP_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from webapp.routers import research, emails

app = FastAPI(
    title="Investigador de Prospectos",
    description="Herramienta de investigación B2B para Faymex",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(WEBAPP_DIR / "templates"))

app.include_router(research.router, prefix="/api", tags=["Research"])
app.include_router(emails.router, prefix="/api", tags=["Emails"])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}
