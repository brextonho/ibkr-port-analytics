"""Summary metrics and the drawdown series, from portfolio_metrics."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from api import schemas
from api.deps import Period, Warehouse, get_warehouse

router = APIRouter()


@router.get("/metrics", response_model=schemas.MetricsSummary | None)
def metrics(wh: Warehouse = Depends(get_warehouse)):
    """Latest metrics row. Stats are inception-to-date / rolling as computed
    by ingestion (§7.8) — the API never recomputes for a sub-period."""
    t = wh.table("portfolio_metrics")
    stmt = select(t).order_by(t.c.report_date.desc()).limit(1)
    with wh.engine.connect() as conn:
        row = conn.execute(stmt).first()
    return dict(row._mapping) if row else None


@router.get("/drawdown", response_model=list[schemas.DrawdownPoint])
def drawdown(period: Period = "1y", wh: Warehouse = Depends(get_warehouse)):
    t = wh.table("portfolio_metrics")
    stmt = select(t.c.report_date, t.c.drawdown_current, t.c.max_drawdown).order_by(
        t.c.report_date
    )
    start = wh.period_start(period)
    if start is not None:
        stmt = stmt.where(t.c.report_date >= start)
    with wh.engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(stmt)]
