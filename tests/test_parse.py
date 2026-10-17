"""What ibflex gives us from the demo year (one statement per business day)."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest


def _first_statement_xml(fixture_xml_path) -> tuple[str, str]:
    """(whole file, its first <FlexStatement>…</FlexStatement> block)."""
    xml = fixture_xml_path.read_text()
    return xml, re.search(r"<FlexStatement .*?</FlexStatement>", xml, re.S).group(0)


def _one_statement_file(tmp_path, fixture_xml_path, edit=lambda s: s):
    xml, first = _first_statement_xml(fixture_xml_path)
    path = tmp_path / "one_day.xml"
    path.write_text(
        '<FlexQueryResponse queryName="t" type="AF"><FlexStatements count="1">\n'
        + edit(first)
        + "\n</FlexStatements></FlexQueryResponse>"
    )
    return path


def test_every_day_is_its_own_statement(stmts, xml_rows):
    assert len(stmts) == len(xml_rows("FlexStatement")) == 260
    assert {s.accountId for s in stmts} == {"DEMO0001"}
    assert all(s.fromDate == s.toDate for s in stmts)
    assert stmts[0].toDate == date(2025, 10, 2) and stmts[-1].toDate == date(2026, 9, 30)


def test_sections_merge_across_statements(frames, xml_rows):
    for frame, tag in [
        ("nav", "EquitySummaryByReportDateInBase"),
        ("positions", "OpenPosition"),
        ("fx_rates", "ConversionRate"),
        ("change_in_nav", "ChangeInNAV"),
        ("cash_transactions", "CashTransaction"),
        ("cash_report", "CashReportCurrency"),
        ("closed_lots", "Lot"),
    ]:
        assert len(frames[frame]) == len(xml_rows(tag)), frame
    assert len(frames["trades"]) == len(xml_rows("Trade"))  # Lots split out


def test_money_arrives_as_decimal_and_dates_as_dates(frames, xml_rows):
    last = frames["change_in_nav"].iloc[-1]
    assert isinstance(last["endingValue"], Decimal)
    assert last["endingValue"] == Decimal(xml_rows("ChangeInNAV")[-1]["endingValue"])
    assert last["toDate"] == date(2026, 9, 30)


def test_one_day_statement_parses_alone(tmp_path, fixture_xml_path):
    from portfolio.flex.parse import parse_statement

    stmt = parse_statement(_one_statement_file(tmp_path, fixture_xml_path))
    assert stmt.toDate == date(2025, 10, 2)


def test_not_ready_pnl_message_refuses_the_statement(tmp_path, fixture_xml_path):
    # IB zeroes every P&L field when its daily run hasn't finished and says
    # so only in a <Message>; ingesting it would overwrite good data with 0s.
    from portfolio.flex.parse import StatementNotReadyError, parse_statements

    path = tmp_path / "not_ready.xml"
    path.write_text(
        fixture_xml_path.read_text().replace(
            "<FlexStatements",
            "<Message>Realized P/L is not ready and has been disabled for this statement.</Message>\n"
            "<FlexStatements",
            1,
        )
    )
    with pytest.raises(StatementNotReadyError):
        parse_statements(path)


def test_closed_lots_split_out_and_tagged_with_closing_trade(tmp_path, fixture_xml_path):
    # IB leaves tradeID blank on <Lot> and lists lots right after the
    # execution that closed them.
    from portfolio.flex.frames import to_frames
    from portfolio.flex.parse import parse_statements

    common = 'accountId="DEMO0001" currency="USD" fxRateToBase="1.3" conid="900106" symbol="NVDA"'
    trades = (
        f'<Trade {common} tradeID="T1" tradeDate="2025-10-02" quantity="-10" '
        'openCloseIndicator="C" levelOfDetail="EXECUTION" />'
        f'<Lot {common} tradeID="" transactionID="O1" tradeDate="2025-10-02" quantity="4" '
        'cost="400" fifoPnlRealized="60" openDateTime="2025-06-10;09:30:00" levelOfDetail="CLOSED_LOT" />'
        f'<Lot {common} tradeID="" transactionID="O2" tradeDate="2025-10-02" quantity="6" '
        'cost="600" fifoPnlRealized="75" openDateTime="2025-06-30;09:30:00" levelOfDetail="CLOSED_LOT" />'
        f'<Trade {common} tradeID="T2" tradeDate="2025-10-02" quantity="5" '
        'openCloseIndicator="O" levelOfDetail="EXECUTION" />'
    )
    path = _one_statement_file(
        tmp_path, fixture_xml_path, lambda s: re.sub(r"<Trades>.*?</Trades>", f"<Trades>{trades}</Trades>", s, flags=re.S)
    )
    frames = to_frames(parse_statements(path))
    assert frames["trades"]["tradeID"].tolist() == ["T1", "T2"]
    assert frames["closed_lots"]["closingTradeID"].tolist() == ["T1", "T1"]
    assert frames["closed_lots"]["transactionID"].tolist() == ["O1", "O2"]


def test_demo_lots_follow_their_sale(frames):
    lots = frames["closed_lots"]
    assert lots["closingTradeID"].notna().all()
    nvda = lots[lots["symbol"] == "NVDA"]
    assert len(nvda) == 2 and nvda["closingTradeID"].nunique() == 1  # one sale, two purchase lots
