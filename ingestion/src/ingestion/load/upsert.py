"""Idempotent upserts: INSERT ... ON CONFLICT (key) DO UPDATE (PRD §5.2).

Every write targets the natural key, so overlapping ingestion windows are
harmless and re-running a window is always safe. Postgres is the target;
SQLite is supported because both dialects implement on_conflict_do_update.

Writes are chunked to stay under each dialect's bind-parameter ceiling, and
rows sharing a conflict key are collapsed first — a backfill over a
day-segmented Flex pull hits both limits.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Sequence

from sqlalchemy import Connection, Table
from sqlalchemy.dialects import postgresql, sqlite

# Bind-parameter ceilings per statement, with headroom: Postgres allows 65535;
# SQLite raised its limit from 999 to 32766 in 3.32, so it is probed rather
# than assumed. A day-segmented 365-day pull produces thousands of position
# rows, which multiplied by column count blows past both.
_SQLITE_LIMIT = 30000 if sqlite3.sqlite_version_info >= (3, 32) else 900
MAX_BIND_PARAMS = {"postgresql": 60000, "sqlite": _SQLITE_LIMIT}


def _dedupe(rows: list[dict[str, Any]], conflict_cols: Sequence[str]) -> list[dict[str, Any]]:
    """Collapse rows sharing a conflict key, keeping the last occurrence.

    A day-segmented Flex pull repeats invariant sections once per statement
    (the same conid appears in every day's SecuritiesInfo), and Postgres
    rejects an ON CONFLICT DO UPDATE that would touch one row twice in a
    single statement. Last-wins matches the upsert's own semantics.
    """
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        seen[tuple(row.get(c) for c in conflict_cols)] = row
    return list(seen.values())


def upsert_rows(
    conn: Connection,
    table: Table,
    rows: list[dict[str, Any]],
    conflict_cols: Sequence[str] | None = None,
) -> int:
    """Upsert rows on the natural key; returns the number of rows written.

    conflict_cols defaults to the table's primary key. Pass explicitly for
    tables whose natural key is a UNIQUE constraint over a surrogate id
    (exposures, fx_attribution). Rows sharing a conflict key are collapsed
    last-wins before the insert.
    """
    if not rows:
        return 0
    if conflict_cols is None:
        conflict_cols = [c.name for c in table.primary_key.columns]
    rows = _dedupe(rows, conflict_cols)

    dialect = conn.dialect.name
    if dialect == "postgresql":
        insert = postgresql.insert
    elif dialect == "sqlite":
        insert = sqlite.insert
    else:
        raise NotImplementedError(f"upsert not implemented for dialect {dialect!r}")

    n_cols = max(len(row) for row in rows)
    chunk_size = max(1, MAX_BIND_PARAMS[dialect] // max(n_cols, 1))
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = insert(table).values(chunk)
        update_cols = {
            c.name: getattr(stmt.excluded, c.name)
            for c in table.columns
            if c.name not in set(conflict_cols) and c.name in chunk[0]
        }
        if update_cols:
            stmt = stmt.on_conflict_do_update(
                index_elements=list(conflict_cols), set_=update_cols
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=list(conflict_cols))
        conn.execute(stmt)
    return len(rows)
