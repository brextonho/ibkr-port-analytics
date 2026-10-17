"""Exposure cuts: one WHERE over the long-format mart (PRD §6.4)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from api import schemas
from api.deps import Warehouse, get_warehouse

router = APIRouter()

Dimension = Literal["asset_class", "geography", "currency", "sector", "theme"]


@router.get("/exposures", response_model=list[schemas.ExposureSlice])
def exposures(by: Dimension = "asset_class", wh: Warehouse = Depends(get_warehouse)):
    """Latest snapshot for the requested dimension. sector/theme are valid
    but unpopulated in MVP — they return empty arrays, not errors (§10.2)."""
    t = wh.table("exposures")
    latest = (
        select(func.max(t.c.snapshot_date)).where(t.c.dimension == by).scalar_subquery()
    )
    stmt = (
        select(t.c.snapshot_date, t.c.dimension, t.c.bucket, t.c.value_sgd, t.c.pct_of_nav)
        .where(t.c.dimension == by, t.c.snapshot_date == latest)
        .order_by(t.c.value_sgd.desc())
    )
    with wh.engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(stmt)]
