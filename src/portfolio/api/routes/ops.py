"""Ops tab: recent ingest runs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Engine, select

from portfolio.api import schemas
from portfolio.api.deps import get_engine, table

router = APIRouter()


@router.get("/ops/runs", response_model=list[schemas.IngestRunRow])
def runs(n: int = Query(default=10, ge=1, le=100), engine: Engine = Depends(get_engine)):
    t = table("ingest_runs")
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(select(t).order_by(t.c.id.desc()).limit(n))]
