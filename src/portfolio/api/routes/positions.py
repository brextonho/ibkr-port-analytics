"""Positions grid, your annotations on them, and exposure cuts — all from the
latest snapshot. Annotation edits write only to the annotations table."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.dialects.sqlite import insert

from portfolio.api import schemas
from portfolio.api.deps import get_engine, table

router = APIRouter()

Dimension = Literal["asset_class", "currency", "geography", "sleeve", "theme", "sector"]

ASSET_CLASSES = ["cash", "stock", "options", "bonds", "funds", "crypto"]


@router.get("/positions", response_model=list[schemas.PositionRow])
def positions(engine: Engine = Depends(get_engine)):
    p, s, a = table("positions"), table("securities"), table("annotations")
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
            p.c.position_value_sgd,
            p.c.percent_of_nav,
            p.c.unrealized_pnl,
            p.c.unrealized_capital_gains_pnl,
            p.c.unrealized_fx_pnl,
            s.c.issuer_country_code,
            a.c.sleeve,
            a.c.theme,
            a.c.sector,
            a.c.geography,
            a.c.thesis,
            a.c.target_price,
            a.c.sellable_date,
        )
        .select_from(p.join(s, p.c.conid == s.c.conid).outerjoin(a, a.c.conid == p.c.conid))
        .where(p.c.snapshot_date == latest)
        .order_by(p.c.position_value_sgd.desc())
    )
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(stmt)]


@router.put("/positions/{conid}", response_model=schemas.AnnotationRow)
def put_annotation(conid: str, body: schemas.AnnotationUpdate, engine: Engine = Depends(get_engine)):
    s, a = table("securities"), table("annotations")
    values = {**body.model_dump(exclude_unset=True), "updated_at": datetime.now(timezone.utc)}
    with engine.begin() as conn:
        if conn.execute(select(s.c.conid).where(s.c.conid == conid)).first() is None:
            raise HTTPException(status_code=404, detail=f"unknown conid {conid!r}")
        stmt = insert(a).values(conid=conid, **values)
        conn.execute(stmt.on_conflict_do_update(index_elements=["conid"], set_=values))
        row = conn.execute(select(a).where(a.c.conid == conid)).one()
    return dict(row._mapping)


@router.get("/exposures", response_model=list[schemas.ExposureSlice])
def exposures(by: Dimension = "asset_class", engine: Engine = Depends(get_engine)):
    """Latest snapshot split by one dimension. Unlabelled holdings fall in
    'Unassigned' (sleeve/theme/sector) or 'Unknown' (geography)."""
    n = table("nav_history")
    with engine.connect() as conn:
        if by == "asset_class":
            row = conn.execute(select(n).order_by(n.c.report_date.desc()).limit(1)).first()
            if row is None or not row.total:
                return []
            total = float(row.total)
            slices = [
                {"bucket": b, "value_sgd": float(getattr(row, b))}
                for b in ASSET_CLASSES
                if getattr(row, b)
            ]
            out = [
                {**x, "snapshot_date": row.report_date, "dimension": by, "pct_of_nav": x["value_sgd"] / total * 100}
                for x in slices
            ]
            return sorted(out, key=lambda x: -x["value_sgd"])

        p, s, a = table("positions"), table("securities"), table("annotations")
        bucket = {
            "currency": p.c.currency,
            "geography": func.coalesce(a.c.geography, s.c.issuer_country_code, "Unknown"),
            "sleeve": func.coalesce(a.c.sleeve, "Unassigned"),
            "theme": func.coalesce(a.c.theme, "Unassigned"),
            "sector": func.coalesce(a.c.sector, "Unassigned"),
        }[by].label("bucket")
        latest = select(func.max(p.c.snapshot_date)).scalar_subquery()
        value = func.sum(p.c.position_value_sgd)
        stmt = (
            select(
                p.c.snapshot_date,
                bucket,
                value.label("value_sgd"),
                (value / func.nullif(n.c.total, 0) * 100).label("pct_of_nav"),
            )
            .select_from(
                p.join(s, s.c.conid == p.c.conid)
                .outerjoin(a, a.c.conid == p.c.conid)
                .outerjoin(n, n.c.report_date == p.c.snapshot_date)
            )
            .where(p.c.snapshot_date == latest)
            .group_by(p.c.snapshot_date, bucket, n.c.total)
            .order_by(value.desc())
        )
        return [{**dict(r._mapping), "dimension": by} for r in conn.execute(stmt)]
