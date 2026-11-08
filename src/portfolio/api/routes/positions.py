"""Positions grid (holdings plus one cash row per currency), your annotations
on them, and exposure cuts — all from the latest snapshot. Annotation edits
write only to the annotations table.

Share of NAV is value ÷ NAV for every row. IB's own percentOfNAV is each
holding's share of invested value (it sums to 100% without cash), so it is
not used here.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Connection, Engine, and_, case, func, select
from sqlalchemy.dialects.sqlite import insert

from portfolio.api import schemas
from portfolio.api.deps import get_engine, table
from portfolio.load.read import stored_base_currency

router = APIRouter()

Dimension = Literal["asset_class", "currency", "geography", "sleeve", "theme", "sector"]

ASSET_CLASSES = ["cash", "stock", "options", "bonds", "funds", "crypto"]

CASH_PREFIX = "CASH."  # cash rows are keyed CASH.<currency> wherever a conid goes


def _rows(conn: Connection) -> list[dict[str, Any]]:
    """Latest holdings ⋈ securities ⋈ annotations, then the cash rows."""
    p, s, a, n = table("positions"), table("securities"), table("annotations"), table("nav_history")
    latest = select(func.max(p.c.snapshot_date)).scalar_subquery()
    stmt = (
        select(
            p.c.snapshot_date,
            p.c.conid,
            s.c.symbol,
            s.c.description,
            s.c.asset_category,
            s.c.sub_category,
            p.c.currency,
            p.c.quantity,
            p.c.mark_price,
            # local cost = local value − price P&L converted back at today's rate;
            # exact, because IB books the FX part separately (unrealized_fx_pnl)
            (
                (p.c.position_value - p.c.unrealized_capital_gains_pnl / func.nullif(p.c.fx_rate_to_base, 0))
                / func.nullif(p.c.quantity, 0)
            ).label("avg_cost_local"),
            p.c.fx_rate_to_base,
            p.c.cost_basis_money,
            p.c.position_value_base,
            (p.c.position_value_base / func.nullif(n.c.total, 0) * 100).label("percent_of_nav"),
            p.c.unrealized_pnl,
            p.c.unrealized_capital_gains_pnl,
            p.c.unrealized_fx_pnl,
            s.c.issuer_country_code,
            *_annotation_columns(a),
        )
        .select_from(
            p.join(s, p.c.conid == s.c.conid)
            .outerjoin(a, a.c.conid == p.c.conid)
            .outerjoin(n, n.c.report_date == p.c.snapshot_date)
        )
        .where(p.c.snapshot_date == latest)
        .order_by(p.c.position_value_base.desc())
    )
    rows = [dict(r._mapping) for r in conn.execute(stmt)]
    return rows + _cash_rows(conn, rows[0]["snapshot_date"]) if rows else rows


def _annotation_columns(a):
    return (a.c.sleeve, a.c.theme, a.c.sector, a.c.geography, a.c.thesis, a.c.target_price, a.c.sellable_date)


def _cash_rows(conn: Connection, day) -> list[dict[str, Any]]:
    """One row per currency held as cash on `day`, valued in base currency at
    that day's rate, so the Positions table adds up to the whole account."""
    c, f, n, a = table("cash_balances"), table("fx_rates"), table("nav_history"), table("annotations")
    rate = func.coalesce(f.c.rate_to_base, case((c.c.currency == stored_base_currency(conn), 1.0)))
    stmt = (
        select(c.c.currency, c.c.ending_cash, (c.c.ending_cash * rate).label("value"), n.c.total, *_annotation_columns(a))
        .select_from(
            c.outerjoin(f, and_(f.c.rate_date == c.c.report_date, f.c.currency == c.c.currency))
            .outerjoin(n, n.c.report_date == c.c.report_date)
            .outerjoin(a, a.c.conid == CASH_PREFIX + c.c.currency)
        )
        # skip dust: IB leaves fractions of a cent behind after conversions
        .where(c.c.report_date == day, c.c.currency != "BASE_SUMMARY", func.abs(c.c.ending_cash) >= 0.005)
    )
    out = []
    for r in conn.execute(stmt):
        row = dict(r._mapping)
        out.append(
            {
                **CASH_ROW,
                **{k: row[k] for k in ("sleeve", "theme", "sector", "geography", "thesis", "target_price", "sellable_date")},
                "snapshot_date": day,
                "conid": CASH_PREFIX + r.currency,
                "symbol": "Cash",
                "description": f"{r.currency} cash",
                "currency": r.currency,
                "quantity": r.ending_cash,
                "fx_rate_to_base": r.value / r.ending_cash if r.value is not None else None,
                "position_value_base": r.value,
                "percent_of_nav": r.value / r.total * 100 if r.value is not None and r.total else None,
            }
        )
    return out


CASH_ROW = {k: None for k in schemas.PositionRow.model_fields} | {"asset_category": "CASH"}


@router.get("/positions", response_model=list[schemas.PositionRow])
def positions(engine: Engine = Depends(get_engine)):
    with engine.connect() as conn:
        return _rows(conn)


@router.put("/positions/{conid}", response_model=schemas.AnnotationRow)
def put_annotation(conid: str, body: schemas.AnnotationUpdate, engine: Engine = Depends(get_engine)):
    s, a, c = table("securities"), table("annotations"), table("cash_balances")
    values = {**body.model_dump(exclude_unset=True), "updated_at": datetime.now(timezone.utc)}
    with engine.begin() as conn:
        if conid.startswith(CASH_PREFIX):
            known = select(c.c.currency).where(c.c.currency == conid.removeprefix(CASH_PREFIX))
        else:
            known = select(s.c.conid).where(s.c.conid == conid)
        if conn.execute(known.limit(1)).first() is None:
            raise HTTPException(status_code=404, detail=f"unknown conid {conid!r}")
        stmt = insert(a).values(conid=conid, **values)
        conn.execute(stmt.on_conflict_do_update(index_elements=["conid"], set_=values))
        row = conn.execute(select(a).where(a.c.conid == conid)).one()
    return dict(row._mapping)


def _bucket(row: dict[str, Any], by: Dimension) -> str:
    if by == "currency":
        return row["currency"]
    if by == "geography":
        default = "Cash" if row["asset_category"] == "CASH" else row["issuer_country_code"] or "Unknown"
        return row["geography"] or default
    return row[by] or "Unassigned"


@router.get("/exposures", response_model=list[schemas.ExposureSlice])
def exposures(by: Dimension = "asset_class", engine: Engine = Depends(get_engine)):
    """Latest snapshot split by one dimension, cash included. Unlabelled rows
    fall in 'Unassigned' (sleeve/theme/sector)."""
    with engine.connect() as conn:
        if by == "asset_class":
            n = table("nav_history")
            row = conn.execute(select(n).order_by(n.c.report_date.desc()).limit(1)).first()
            if row is None or not row.total:
                return []
            total = float(row.total)
            out = [
                {
                    "snapshot_date": row.report_date,
                    "dimension": by,
                    "bucket": b,
                    "value_base": float(getattr(row, b)),
                    "pct_of_nav": float(getattr(row, b)) / total * 100,
                }
                for b in ASSET_CLASSES
                if getattr(row, b)
            ]
            return sorted(out, key=lambda x: -x["value_base"])
        rows = _rows(conn)

    value: dict[str, float] = defaultdict(float)
    share: dict[str, float] = defaultdict(float)
    for r in rows:
        key = _bucket(r, by)
        value[key] += float(r["position_value_base"] or 0)
        share[key] += float(r["percent_of_nav"] or 0)
    return [
        {"snapshot_date": rows[0]["snapshot_date"], "dimension": by, "bucket": k, "value_base": v, "pct_of_nav": share[k]}
        for k, v in sorted(value.items(), key=lambda kv: -kv[1])
    ]
