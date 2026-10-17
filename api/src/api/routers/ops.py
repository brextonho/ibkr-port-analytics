"""Ops panel: recent ingestion runs, watermark, retry history (§11.3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from api import schemas
from api.deps import Warehouse, get_warehouse

router = APIRouter()


@router.get("/ops/runs", response_model=list[schemas.IngestRunRow])
def runs(
    n: int = Query(default=10, ge=1, le=100),
    wh: Warehouse = Depends(get_warehouse),
):
    t = wh.table("ingest_runs")
    stmt = select(t).order_by(t.c.id.desc()).limit(n)
    with wh.engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(stmt)]
