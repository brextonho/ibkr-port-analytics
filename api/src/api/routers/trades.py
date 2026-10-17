"""Trade journal, aggregate stats, and the process-grade write path (§10.3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from api import schemas
from api.deps import Warehouse, get_warehouse

router = APIRouter()


@router.get("/trades/journal", response_model=list[schemas.JournalRow])
def journal(wh: Warehouse = Depends(get_warehouse)):
    t = wh.table("trade_journal")
    stmt = select(t).order_by(t.c.close_date.desc())
    with wh.engine.connect() as conn:
        return [dict(row._mapping) for row in conn.execute(stmt)]


@router.get("/trades/stats", response_model=schemas.TradeStats | None)
def stats(wh: Warehouse = Depends(get_warehouse)):
    t = wh.table("trade_stats")
    stmt = select(t).order_by(t.c.as_of_date.desc()).limit(1)
    with wh.engine.connect() as conn:
        row = conn.execute(stmt).first()
    return dict(row._mapping) if row else None


@router.put("/trades/{trade_id}/grade", response_model=schemas.JournalRow)
def put_grade(
    trade_id: str, body: schemas.GradeUpdate, wh: Warehouse = Depends(get_warehouse)
):
    """Grade the process, not the outcome (§7.9). Only touches process_grade."""
    t = wh.table("trade_journal")
    with wh.engine.begin() as conn:
        result = conn.execute(
            t.update()
            .where(t.c.trade_id == trade_id)
            .values(process_grade=body.process_grade)
        )
        if result.rowcount == 0:
            raise HTTPException(
                status_code=404, detail=f"no journal row for trade {trade_id!r}"
            )
        row = conn.execute(select(t).where(t.c.trade_id == trade_id)).first()
    assert row is not None
    return dict(row._mapping)
