"""The base currency comes from the statements, and one database holds one."""
from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

import portfolio.ingest as ingest
from portfolio.config import FlexSettings, Settings
from portfolio.flex.client import FlexFatalError
from portfolio.flex.parse import parse_statements
from portfolio.ingest import run, statement_base_currency
from portfolio.load.db import make_engine
from portfolio.load.models import Base, NavHistory
from portfolio.load.watermark import current_watermark
from portfolio.transform import IncompleteSectionError

FIXTURES = Path(__file__).parent / "fixtures"


def test_a_second_base_currency_is_refused_and_nothing_is_written(tmp_path):
    settings = Settings(database=str(tmp_path / "p.db"))
    assert run(settings, xml_paths=[FIXTURES / "test_data.xml"], benchmark=False) == 0
    assert run(settings, xml_paths=[FIXTURES / "test_usd.xml"], benchmark=False) == 1
    engine = make_engine(settings.database_url)
    with engine.connect() as conn:
        assert set(conn.execute(select(NavHistory.base_currency)).scalars()) == {"SGD"}
        last = conn.execute(select(Base.metadata.tables["ingest_runs"]).order_by("id")).all()[-1]
    assert last.error_code == "BaseCurrencyChangedError"
    assert "USD" in last.error_message and "SGD" in last.error_message


def test_statement_without_account_information_says_how_to_fix_it():
    xml = (FIXTURES / "test_usd.xml").read_text()
    stmts = parse_statements(re.sub(r"<AccountInformation [^>]*/>", "", xml).encode())
    with pytest.raises(IncompleteSectionError, match="Account Information"):
        statement_base_currency(stmts)


def test_live_pull_steps_td_back_on_1003_until_a_statement_exists(tmp_path, monkeypatch):
    xml = (FIXTURES / "test_data.xml").read_bytes()
    tds = []

    def fake_fetch(flex, *, from_date, to_date, retry):
        tds.append(to_date)
        if len(tds) < 3:
            raise FlexFatalError(1003, "Statement is not available.")
        return xml, []

    monkeypatch.setattr(ingest, "fetch_statement", fake_fetch)
    monkeypatch.setattr(ingest, "LIVE_XML_DIR", tmp_path / "xml")
    settings = Settings(database=str(tmp_path / "p.db"), flex=FlexSettings(query_id="1", token="t"))
    assert run(settings, xml_paths=[FIXTURES / "test_data.xml"], benchmark=False) == 0
    assert run(settings, benchmark=False) == 0
    assert tds[1:] == [tds[0] - timedelta(days=1), tds[0] - timedelta(days=2)]
    assert list((tmp_path / "xml").glob(f"*_{tds[2]:%Y%m%d}.xml"))


def test_live_pull_stops_stepping_back_at_the_watermark(tmp_path, monkeypatch):
    tds = []

    def fake_fetch(flex, *, from_date, to_date, retry):
        tds.append((from_date, to_date))
        raise FlexFatalError(1003, "Statement is not available.")

    monkeypatch.setattr(ingest, "fetch_statement", fake_fetch)
    settings = Settings(database=str(tmp_path / "p.db"), flex=FlexSettings(query_id="1", token="t"))
    assert run(settings, xml_paths=[FIXTURES / "test_data.xml"], benchmark=False) == 0
    with make_engine(settings.database_url).connect() as conn:
        watermark = current_watermark(conn)
    assert run(settings, benchmark=False) == 1
    from_date = tds[0][0]
    assert tds[-1][1] == max(watermark, from_date)
    assert len(tds) == (tds[0][1] - tds[-1][1]).days + 1
