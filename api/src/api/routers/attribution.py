"""FX attribution rows (PRD §7.6): the SGD drag, by currency, over time."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from api import schemas
from api.deps import Period, Warehouse, get_warehouse

router = APIRouter()


@router.get("/attribution/fx", response_model=list[schemas.FxAttributionRow])
def fx_attribution(period: Period = "1y", wh: Warehouse = Depends(get_warehouse)):
    t = wh.table("fx_attribution")
    stmt = select(
        t.c.report_date, t.c.currency, t.c.weight, t.c.fx_return, t.c.contribution_bps
    ).order_by(t.c.report_date, t.c.currency)
    start = wh.period_start(period)
    if start is not None:
        stmt = stmt.where(t.c.report_date >= start)
    with wh.engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(stmt)]
