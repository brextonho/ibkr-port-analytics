"""External-flow classification (PRD §7.4).

External = capital crossing the account boundary; everything else is return.
Whitelist explicitly in BOTH directions — an unrecognised type raises instead
of silently defaulting, because a silent default is exactly where the classic
dividends-as-flows TWR bug comes from.
"""
from __future__ import annotations

import enum
import pandas as pd

from ibflex.enums import CashAction

EXTERNAL_TYPES = frozenset(
    {
        CashAction.DEPOSITWITHDRAW.value,  # "Deposits & Withdrawals"
        "Deposits/Withdrawals",  # string variant seen in raw Flex XML
    }
)

INTERNAL_TYPES = frozenset(
    {
        CashAction.DIVIDEND.value,
        CashAction.PAYMENTINLIEU.value,
        CashAction.WHTAX.value,
        CashAction.BROKERINTPAID.value,
        CashAction.BROKERINTRCVD.value,
        CashAction.BONDINTPAID.value,
        CashAction.BONDINTRCVD.value,
        CashAction.FEES.value,
        CashAction.COMMADJ.value,
        CashAction.ADVISORFEES.value,
    }
)


class UnknownFlowTypeError(Exception):
    """A cash transaction type outside both whitelists. User to check and classify."""


def external_flow_series(cash_transactions) -> pd.Series:
    """Net external flow (SGD) per calendar date, from classified rows."""
    import pandas as pd

    if cash_transactions.empty or "is_external_flow" not in cash_transactions.columns:
        return pd.Series(dtype=float)
    external = cash_transactions[cash_transactions["is_external_flow"].astype(bool)]
    if external.empty:
        return pd.Series(dtype=float)
    dates = pd.to_datetime(external["date_time"]).dt.normalize()
    return external["amount_sgd"].astype(float).groupby(dates).sum().sort_index()


def cross_check_against_change_in_nav(
    flow_total: float, change_in_nav, *, tolerance: float = 0.01
) -> tuple[bool, float]:
    """§7.4: summed external flows should tie to IB's deposits_withdrawals.

    Returns (ties, difference). Callers log a warning on mismatch — the two
    series cover the same window only when marts are computed over the full
    ingested history.
    """
    if change_in_nav.empty or "deposits_withdrawals" not in change_in_nav.columns:
        return True, 0.0
    reported = float(change_in_nav["deposits_withdrawals"].astype(float).sum())
    diff = flow_total - reported
    return abs(diff) <= tolerance, diff


def is_external_flow(txn_type: object) -> bool:
    """Classify one cash-transaction type. Accepts the ibflex enum or its string."""
    value = txn_type.value if isinstance(txn_type, enum.Enum) else txn_type
    if value in EXTERNAL_TYPES:
        return True
    if value in INTERNAL_TYPES:
        return False
    raise UnknownFlowTypeError(
        f"unrecognised cash transaction type {value!r}: add it to EXTERNAL_TYPES "
        f"or INTERNAL_TYPES in {__name__} after deciding which side it belongs on"
    )
