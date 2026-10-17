"""Flow classification (PRD §7.4): the classic bug lives here."""
from __future__ import annotations

import pytest
from ibflex.enums import CashAction

from ingestion.analytics.flows import UnknownFlowTypeError, is_external_flow


def test_deposits_are_external():
    assert is_external_flow(CashAction.DEPOSITWITHDRAW) is True
    assert is_external_flow("Deposits & Withdrawals") is True


def test_dividends_are_return_not_flow():
    assert is_external_flow(CashAction.DIVIDEND) is False
    assert is_external_flow("Dividends") is False


def test_costs_and_income_are_internal():
    for action in (
        CashAction.WHTAX,
        CashAction.BROKERINTPAID,
        CashAction.BROKERINTRCVD,
        CashAction.FEES,
        CashAction.PAYMENTINLIEU,
    ):
        assert is_external_flow(action) is False


def test_unknown_type_raises_instead_of_guessing():
    with pytest.raises(UnknownFlowTypeError):
        is_external_flow("Mystery Transfer")
