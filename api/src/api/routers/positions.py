"""Positions grid and the position-notes write path (PRD §10.3).

The PUT writes to the user-maintained position_notes table only — never to
marts, never to raw.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from api import schemas
from api.deps import Warehouse, get_warehouse

router = APIRouter()


@router.get("/positions", response_model=list[schemas.PositionRow])
def positions(wh: Warehouse = Depends(get_warehouse)):
    """Latest snapshot ⋈ securities ⋈ security_tags ⋈ position_notes."""
    p = wh.table("positions")
    s = wh.table("securities")
    tags = wh.table("security_tags")
    notes = wh.table("position_notes")

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
            p.c.fx_rate_to_base,
            p.c.cost_basis_price,
            p.c.cost_basis_money,
            p.c.position_value_sgd,
            p.c.percent_of_nav,
            p.c.unrealized_pnl,
            s.c.issuer_country_code,
            tags.c.geography,
            tags.c.theme,
            notes.c.thesis,
            notes.c.catalyst_date,
            notes.c.target_price,
            notes.c.base_price,
            notes.c.bear_price,
            notes.c.sellable_date,
        )
        .select_from(
            p.join(s, p.c.conid == s.c.conid)
            .outerjoin(tags, tags.c.conid == p.c.conid)
            .outerjoin(notes, notes.c.conid == p.c.conid)
        )
        .where(p.c.snapshot_date == latest)
        .order_by(p.c.position_value_sgd.desc())
    )
    with wh.engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(stmt)]


@router.put("/positions/{conid}/notes", response_model=schemas.PositionNoteRow)
def put_notes(
    conid: str,
    body: schemas.PositionNotesUpdate,
    wh: Warehouse = Depends(get_warehouse),
):
    securities = wh.table("securities")
    notes = wh.table("position_notes")
    updates = body.model_dump(exclude_unset=True)
    updates["updated_at"] = datetime.now(timezone.utc)

    with wh.engine.begin() as conn:
        known = conn.execute(
            select(securities.c.conid).where(securities.c.conid == conid)
        ).first()
        if known is None:
            raise HTTPException(status_code=404, detail=f"unknown conid {conid!r}")
        exists = conn.execute(
            select(notes.c.conid).where(notes.c.conid == conid)
        ).first()
        if exists:
            conn.execute(notes.update().where(notes.c.conid == conid).values(**updates))
        else:
            conn.execute(notes.insert().values(conid=conid, **updates))
        row = conn.execute(select(notes).where(notes.c.conid == conid)).first()
    assert row is not None
    return dict(row._mapping)
