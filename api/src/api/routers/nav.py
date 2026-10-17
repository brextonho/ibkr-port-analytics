"""NAV curve and daily return series, both from daily_returns."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from api import schemas
from api.deps import Period, Warehouse, get_warehouse, period_start

router = APIRouter()


def _series(wh: Warehouse, period: Period, columns: list[str]) -> list[dict]:
    t = wh.table("daily_returns")
    stmt = select(*(t.c[c] for c in columns)).order_by(t.c.report_date)
    start = period_start(period)
    if start is not None:
        stmt = stmt.where(t.c.report_date >= start)
    with wh.engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(stmt)]


@router.get("/nav", response_model=list[schemas.NavPoint])
def nav(period: Period = "1y", wh: Warehouse = Depends(get_warehouse)):
    return _series(
        wh, period, ["report_date", "nav_sgd", "external_flow_sgd", "benchmark_cum"]
    )


@router.get("/returns", response_model=list[schemas.ReturnPoint])
def returns(period: Period = "1y", wh: Warehouse = Depends(get_warehouse)):
    return _series(
        wh,
        period,
        [
            "report_date",
            "r_period",
            "r_local",
            "r_fx",
            "cum_twr",
            "benchmark_r",
            "benchmark_cum",
        ],
    )
