"""XML → ibflex objects (PRD §5.5)."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from ibflex import parser
from ibflex.Types import FlexStatement


def parse_statements(source: bytes | str | Path) -> tuple[FlexStatement, ...]:
    """Parse Flex XML from a path or raw bytes into one statement per period.

    With `Breakout by Day = Yes` (PRD §4.1) IB segments a multi-day window
    into one <FlexStatement> per day rather than one row per day inside a
    single statement — a 365-day pull returns ~260 of them. A single-day pull
    (the fixture) returns exactly one. Both shapes are normal; the caller
    merges the sections (§5.5).
    """
    if isinstance(source, bytes):
        response = parser.parse(BytesIO(source))
    else:
        response = parser.parse(str(source))
    statements = tuple(response.FlexStatements)
    if not statements:
        raise ValueError("Flex response contains no FlexStatement")
    accounts = {s.accountId for s in statements}
    if len(accounts) > 1:
        raise ValueError(f"expected a single account, got {sorted(accounts)}")
    return statements


def parse_statement(source: bytes | str | Path) -> FlexStatement:
    """Single-statement accessor; raises if the pull was segmented by day."""
    statements = parse_statements(source)
    if len(statements) != 1:
        raise ValueError(f"expected exactly 1 FlexStatement, got {len(statements)}")
    return statements[0]
