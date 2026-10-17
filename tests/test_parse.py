"""The fixture is a censored real Flex pull; these tests pin what ibflex gives us."""
from __future__ import annotations

from datetime import date
from decimal import Decimal


def test_statement_identity(stmt):
    assert stmt.accountId == "DEMO0001"
    assert stmt.fromDate == date(2026, 7, 15)
    assert stmt.toDate == date(2026, 7, 15)


def test_section_row_counts(frames):
    assert len(frames["nav"]) == 2  # prior-date anchor row + report day (§4.3)
    assert len(frames["positions"]) == 7
    assert len(frames["securities"]) == 7
    assert len(frames["fx_rates"]) == 6
    assert len(frames["change_in_nav"]) == 1
    assert frames["trades"].empty
    assert frames["cash_transactions"].empty


def test_money_arrives_as_decimal_and_dates_as_dates(frames):
    nav = frames["nav"].sort_values("reportDate").iloc[-1]
    assert isinstance(nav["total"], Decimal)
    assert nav["total"] == Decimal("96711.27489")
    assert nav["reportDate"] == date(2026, 7, 15)


def test_change_in_nav_carries_the_twr_oracle(frames):
    row = frames["change_in_nav"].iloc[0]
    assert row["twr"] == Decimal("0.6235337558")
    assert row["fxTranslation"] == Decimal("0.75024")
    assert row["depositsWithdrawals"] == Decimal("0")


def test_day_segmented_pull_parses_every_statement(tmp_path, fixture_xml_path):
    # Breakout by Day segments a multi-day window into one <FlexStatement>
    # per day (PRD §4.1); the fixture is a one-day pull, so fabricate a
    # second segment from it.
    import re

    from ingestion.flex.parse import parse_statements

    xml = fixture_xml_path.read_text()
    one = re.search(r"<FlexStatement .*?</FlexStatement>", xml, re.S).group(0)
    two = one.replace("2026-07-15", "2026-07-16")
    path = tmp_path / "segmented.xml"
    path.write_text(
        xml.replace(one, one + two).replace(
            '<FlexStatements count="1">', '<FlexStatements count="2">'
        )
    )

    stmts = parse_statements(path)
    assert len(stmts) == 2
    assert [s.toDate for s in stmts] == [date(2026, 7, 15), date(2026, 7, 16)]


def test_segments_merge_into_one_frame_per_section(stmt, frames):
    from ingestion.flex.frames import to_frames

    merged = to_frames([stmt, stmt])
    for name, frame in frames.items():
        assert len(merged[name]) == 2 * len(frame), name
