"""FastAPI app: JSON under /api, and the built dashboard (web/dist) at /."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from portfolio.api import schemas
from portfolio.api.routes import income, ops, performance, positions, trades
from portfolio.load.db import make_engine

WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"


def create_app(database_url: str, *, risk_free_rate: float = 0.0, base_currency: str = "SGD") -> FastAPI:
    app = FastAPI(title="IBKR Portfolio Analytics", version="0.2.0")
    app.state.engine = make_engine(database_url)
    app.state.risk_free_rate = risk_free_rate
    app.state.base_currency = base_currency

    @app.get("/api/health", response_model=schemas.Health)
    def health():
        return {"status": "ok"}

    for module in (performance, positions, trades, income, ops):
        app.include_router(module.router, prefix="/api")

    @app.middleware("http")
    async def no_stale_page(request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith(("/api/", "/assets/")):
            # recheck the page on every load, so a rebuilt dashboard shows up
            # at once; /assets files have content hashes in their names
            response.headers["Cache-Control"] = "no-cache"
        return response

    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    else:

        @app.get("/", include_in_schema=False)
        def root() -> RedirectResponse:  # no built dashboard yet: show the API docs
            return RedirectResponse("/docs")

    return app
