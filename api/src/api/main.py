"""FastAPI app factory (PRD §10): thin reads over marts, two writes, no IBKR.

Run locally:
    DATABASE_URL=... uvicorn api.main:create_app --factory --reload
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api import schemas
from api.deps import build_warehouse
from api.routers import (
    attribution,
    exposures,
    income,
    metrics,
    nav,
    ops,
    positions,
    trades,
)


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(
        title="IBKR Portfolio Analytics API",
        version="0.1.0",
        description="Read-only serving layer over pre-computed analytics marts. "
        "All computation happens in the ingestion ETL.",
    )
    # the vite dev server proxies /api, but allow direct localhost calls too
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.warehouse = build_warehouse(database_url)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/docs")

    @app.get("/health", response_model=schemas.Health)
    def health():
        return {"status": "ok"}

    for router in (nav, metrics, exposures, attribution, positions, trades, ops, income):
        app.include_router(router.router)
    return app
