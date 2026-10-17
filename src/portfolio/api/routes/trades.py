"""Closed trades, built on request from IB's Closed Lots, with your notes."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.dialects.sqlite import insert

from portfolio.analytics.journal import build_trade_journal
from portfolio.api import schemas
from portfolio.api.deps import get_engine, table

router = APIRouter()


@router.get("/closed-trades", response_model=list[schemas.ClosedTrade])
def closed_trades(engine: Engine = Depends(get_engine)):
    with engine.connect() as conn:
        lots = pd.read_sql(select(table("closed_lots")), conn)
        securities = pd.read_sql(select(table("securities")), conn)
        notes = pd.read_sql(select(table("trade_notes")), conn)
    journal = build_trade_journal(lots, securities)
    if journal.empty:
        return []
    journal = journal.merge(notes[["trade_id", "note"]], on="trade_id", how="left")
    journal = journal.sort_values("close_date", ascending=False)
    journal = journal.astype(object).where(pd.notna(journal), None)
    return journal.to_dict(orient="records")


@router.put("/closed-trades/{trade_id}", response_model=schemas.NoteUpdate)
def put_note(trade_id: str, body: schemas.NoteUpdate, engine: Engine = Depends(get_engine)):
    lots, notes = table("closed_lots"), table("trade_notes")
    values = {"note": body.note, "updated_at": datetime.now(timezone.utc)}
    with engine.begin() as conn:
        if conn.execute(select(lots.c.trade_id).where(lots.c.trade_id == trade_id)).first() is None:
            raise HTTPException(status_code=404, detail=f"no closed trade {trade_id!r}")
        stmt = insert(notes).values(trade_id=trade_id, **values)
        conn.execute(stmt.on_conflict_do_update(index_elements=["trade_id"], set_=values))
    return {"note": body.note}
