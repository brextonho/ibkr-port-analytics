"""XML → ibflex objects (PRD §5.5)."""
from __future__ import annotations

import logging
import re
from io import BytesIO
from pathlib import Path

from ibflex import parser
from ibflex.Types import FlexStatement

logger = logging.getLogger(__name__)

_MESSAGE = re.compile(rb"<Message>(.*?)</Message>", re.DOTALL)


class StatementNotReadyError(Exception):
    """IB flagged the statement's P&L as not final; ingesting it would store zeros."""


def check_messages(xml: bytes) -> None:
    """Fail on IB's "Realized P/L is not ready" notice; log any other <Message>.

    ibflex skips <Message> elements, but when IB's daily P&L run hasn't
    finished it zeroes every cost-basis and P&L field and says so only here.
    """
    for raw in _MESSAGE.findall(xml):
        message = raw.decode(errors="replace").strip()
        if "not ready" in message.lower():
            raise StatementNotReadyError(
                f"IB: {message!r} — re-pull later, or exclude the last day from a "
                "manual download"
            )
        logger.warning("IB statement message: %s", message)


def parse_statements(source: bytes | str | Path) -> tuple[FlexStatement, ...]:
    """Parse Flex XML from a path or raw bytes into one statement per period.

    With `Breakout by Day = Yes` (PRD §4.1) IB segments a multi-day window
    into one <FlexStatement> per day rather than one row per day inside a
    single statement — a 365-day pull returns ~260 of them. A single-day pull
    (the fixture) returns exactly one. Both shapes are normal; the caller
    merges the sections (§5.5).
    """
    xml = source if isinstance(source, bytes) else Path(source).read_bytes()
    check_messages(xml)
    response = parser.parse(BytesIO(xml))
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
