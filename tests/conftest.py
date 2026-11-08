from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from portfolio.flex.frames import to_frames
from portfolio.flex.parse import parse_statements
from portfolio.load.db import make_engine
from portfolio.load.models import Base
from portfolio.load.read import read_frames
from portfolio.load.upsert import upsert_rows
from portfolio.transform import RAW_TABLE_ORDER, transform_all

FIXTURES = Path(__file__).parent / "fixtures"


# the same demo year kept in two base currencies; every test that reads the
# XML runs once per file, so nothing may assume SGD
@pytest.fixture(scope="session", params=["test_data.xml", "test_usd.xml"])
def fixture_xml_path(request) -> Path:
    return FIXTURES / request.param


@pytest.fixture(scope="session")
def stmts(fixture_xml_path):
    """The demo year: one statement per business day (Breakout by Day)."""
    return parse_statements(fixture_xml_path)


@pytest.fixture(scope="session")
def frames(stmts):
    return to_frames(stmts)


@pytest.fixture(scope="session")
def xml_rows(fixture_xml_path):
    """Attributes of every <tag> element, read straight from the XML with the
    standard library — an independent check on what the pipeline produces."""
    root = ET.parse(fixture_xml_path).getroot()
    return lambda tag: [e.attrib for e in root.iter(tag)]


@pytest.fixture(scope="session")
def base_currency(xml_rows) -> str:
    return xml_rows("AccountInformation")[0]["currency"]


@pytest.fixture(scope="session")
def raw_frames(frames, base_currency):
    """Raw tables as the derived-table code reads them: transformed, upserted
    into a scratch database (which collapses rows repeated across days), and
    read back — the production path."""
    rows = transform_all(frames, ingested_at=datetime(2026, 10, 1, tzinfo=timezone.utc), base_currency=base_currency)
    eng = make_engine("sqlite://")
    with eng.begin() as conn:
        for name in RAW_TABLE_ORDER:
            upsert_rows(conn, Base.metadata.tables[name], rows[name])
    return read_frames(eng, [*RAW_TABLE_ORDER, "benchmark_prices"])


@pytest.fixture()
def engine():
    # StaticPool: one shared connection so the in-memory DB survives reconnects
    eng = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(eng)
    return eng
