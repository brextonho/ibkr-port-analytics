"""P&L and income rows: IB's daily Change in NAV breakdown, and dividend /
withholding cash transactions, in base currency as stored."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Engine, and_, select

from portfolio.api import schemas
from portfolio.api.deps import Period, get_engine, start_of, table

router = APIRouter()

DIVIDEND_TYPES = ("Dividends", "Payment In Lieu Of Dividends", "Withholding Tax")


@router.get("/pnl", response_model=list[schemas.PnlPoint])
def pnl(period: Period = "1y", engine: Engine = Depends(get_engine)):
    c, n = table("change_in_nav"), table("nav_history")
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
            c.outerjoin(n, and_(n.c.report_date == c.c.to_date, n.c.account_id == c.c.account_id))
        )
        .where(c.c.from_date == c.c.to_date)  # daily rows only; a summary row would double count
        .order_by(c.c.to_date)
    )
    with engine.connect() as conn:
        if (start := start_of(conn, period)) is not None:
            stmt = stmt.where(c.c.to_date >= start)
        return [dict(r._mapping) for r in conn.execute(stmt)]


@router.get("/dividends", response_model=list[schemas.DividendRow])
def dividends(period: Period = "1y", engine: Engine = Depends(get_engine)):
    t, s = table("cash_transactions"), table("securities")
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
    with engine.connect() as conn:
        if (start := start_of(conn, period)) is not None:
            stmt = stmt.where(t.c.date_time >= start)
        return [dict(r._mapping) for r in conn.execute(stmt)]
