"""ibflex statement objects → pandas DataFrames, one per raw-table concept (PRD §5.5).

Values keep their parsed types here (Decimal, date, datetime, enums); type
coercion for storage happens in transform/.
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

import pandas as pd
from ibflex.Types import FlexStatement, Lot

SECTIONS = {
    "nav": "EquitySummaryInBase",
    "positions": "OpenPositions",
    "trades": "Trades",
    "cash_transactions": "CashTransactions",
    "securities": "SecuritiesInfo",
    "fx_rates": "ConversionRates",
    "change_in_nav": "ChangeInNAV",
}


def _frame(objs: Iterable[Any]) -> pd.DataFrame:
    return pd.DataFrame([vars(o) for o in objs])


def _rows(stmt: FlexStatement, attr: str) -> list[Any]:
    """One section of one statement as a list.

    ChangeInNAV is handled as scalar-or-list because with Breakout by Day the
    section's shape is unconfirmed (§4.7) — the loader must handle either.
    """
    section = getattr(stmt, attr, None)
    if section is None:
        return []
    if isinstance(section, (list, tuple)):
        return list(section)
    return [section]


def _closed_lots(stmt: FlexStatement) -> list[dict[str, Any]]:
    """Closed Lots rows, each tagged with its closing execution's tradeID.

    IB leaves tradeID blank on <Lot> rows and lists them directly after the
    execution that closed them, so document order is the only link.
    """
    out: list[dict[str, Any]] = []
    closing_trade_id = None
    for row in _rows(stmt, "Trades"):
        if isinstance(row, Lot):
            out.append({**vars(row), "closingTradeID": closing_trade_id})
        else:
            closing_trade_id = row.tradeID
    return out


def to_frames(
    stmts: FlexStatement | Sequence[FlexStatement],
) -> dict[str, pd.DataFrame]:
    """Merge one or many statements into one DataFrame per raw-table concept.

    Breakout by Day segments a multi-day window into one statement per day
    (§5.5), so sections are concatenated across statements. Rows repeated
    across days (SecuritiesInfo, the NAV prior-date anchor) are deduplicated
    downstream by the upsert's natural key. Missing sections come back as
    empty DataFrames, never KeyErrors.
    """
    if isinstance(stmts, FlexStatement):
        stmts = [stmts]
    frames = {
        name: _frame(
            [
                row
                for stmt in stmts
                for row in _rows(stmt, attr)
                if not isinstance(row, Lot)  # Trades also holds Closed Lots
            ]
        )
        for name, attr in SECTIONS.items()
    }
    frames["closed_lots"] = pd.DataFrame(
        [lot for stmt in stmts for lot in _closed_lots(stmt)]
    )
    return frames
