"""P&L and income rows: IB's daily Change in NAV breakdown, and dividend /
withholding cash transactions. Rows are served as stored, in base currency;
the dashboard sums them over the selected period.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select

from api import schemas
from api.deps import Period, Warehouse, get_warehouse, period_start

router = APIRouter()

DIVIDEND_TYPES = ("Dividends", "Payment In Lieu Of Dividends", "Withholding Tax")


@router.get("/pnl", response_model=list[schemas.PnlPoint])
def pnl(period: Period = "1y", wh: Warehouse = Depends(get_warehouse)):
    c = wh.table("change_in_nav")
    n = wh.table("nav_history")
    stmt = (
        select(
            c.c.to_date.label("report_date"),
            c.c.ending_value.label("nav_sgd"),
            n.c.cash.label("cash_sgd"),
            c.c.realized,
            c.c.change_in_unrealized,
            c.c.dividends,
            c.c.withholding_tax,
            c.c.interest,
            c.c.commissions,
            c.c.other_fees,
        )
        .select_from(
            c.outerjoin(
                n, and_(n.c.report_date == c.c.to_date, n.c.account_id == c.c.account_id)
            )
        )
        # daily breakout rows only; a period-summary row would double count
        .where(c.c.from_date == c.c.to_date)
        .order_by(c.c.to_date)
    )
    start = period_start(period)
    if start is not None:
        stmt = stmt.where(c.c.to_date >= start)
    with wh.engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(stmt)]


@router.get("/dividends", response_model=list[schemas.DividendRow])
def dividends(period: Period = "1y", wh: Warehouse = Depends(get_warehouse)):
    t = wh.table("cash_transactions")
    s = wh.table("securities")
    stmt = (
        select(
            t.c.transaction_id,
            t.c.date_time,
            t.c.conid,
            s.c.symbol,
            t.c.type,
            t.c.currency,
            t.c.amount,
            t.c.amount_sgd,
        )
        .select_from(t.outerjoin(s, s.c.conid == t.c.conid))
        .where(t.c.type.in_(DIVIDEND_TYPES))
        .order_by(t.c.date_time)
    )
    start = period_start(period)
    if start is not None:
        stmt = stmt.where(t.c.date_time >= start)
    with wh.engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(stmt)]
