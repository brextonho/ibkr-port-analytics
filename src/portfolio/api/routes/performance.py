"""Performance for one period: chart series and risk/return stats, computed
on request from the daily_returns spine; and FX contribution by currency."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Request
from sqlalchemy import Engine, func, select

from portfolio.analytics.stats import performance as compute_performance
from portfolio.api import schemas
from portfolio.api.deps import Period, get_engine, start_of, table

router = APIRouter()


def _frame(engine: Engine, name: str, date_col: str, period: Period) -> pd.DataFrame:
    t = table(name)
    stmt = select(t).order_by(t.c[date_col])
    with engine.connect() as conn:
        if (start := start_of(conn, period)) is not None:
            stmt = stmt.where(t.c[date_col] >= start)
        return pd.read_sql(stmt, conn)


@router.get("/performance", response_model=schemas.Performance | None)
def performance(request: Request, period: Period = "1y", engine: Engine = Depends(get_engine)):
    daily = _frame(engine, "daily_returns", "report_date", period)
    return compute_performance(daily, rf_annual=request.app.state.risk_free_rate)


@router.get("/fx", response_model=list[schemas.FxPoint])
def fx(period: Period = "1y", engine: Engine = Depends(get_engine)):
    """Cumulative FX contribution per currency since the period's first date.

    Daily contributions are summed, so the currencies add up to the period's
    FX return only approximately (no compounding between them).
    """
    dr, fa = table("daily_returns"), table("fx_attribution")
    with engine.connect() as conn:
        base_q = select(func.min(dr.c.report_date))
        if (start := start_of(conn, period)) is not None:
            base_q = base_q.where(dr.c.report_date >= start)
        base = conn.execute(base_q).scalar()
        if base is None:
            return []
        rows = pd.read_sql(select(fa).where(fa.c.report_date > base), conn)
    if rows.empty:
        return []
    rows["report_date"] = pd.to_datetime(rows["report_date"])
    wide = rows.pivot_table(
        index="report_date", columns="currency", values="contribution_bps", aggfunc="sum"
    ).fillna(0.0) / 10_000.0
    wide.loc[pd.Timestamp(base)] = 0.0  # the base point: nothing contributed yet
    cum = wide.sort_index().cumsum().reset_index(names="report_date").melt(
        id_vars="report_date", var_name="currency", value_name="cum_contribution"
    )
    cum["report_date"] = cum["report_date"].dt.date
    return cum.sort_values(["report_date", "currency"]).to_dict(orient="records")
