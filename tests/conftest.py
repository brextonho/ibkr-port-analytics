from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixture_xml_path() -> Path:
    return FIXTURES / "test_data.xml"


@pytest.fixture(scope="session")
def stmts(fixture_xml_path):
    """The demo year: one statement per business day (Breakout by Day)."""
    from portfolio.flex.parse import parse_statements

    return parse_statements(fixture_xml_path)


@pytest.fixture(scope="session")
def frames(stmts):
    from portfolio.flex.frames import to_frames

    return to_frames(stmts)


@pytest.fixture(scope="session")
def xml_rows(fixture_xml_path):
    """Attributes of every <tag> element, read straight from the XML with the
    standard library — an independent check on what the pipeline produces."""
    import xml.etree.ElementTree as ET

    root = ET.parse(fixture_xml_path).getroot()
    return lambda tag: [e.attrib for e in root.iter(tag)]


@pytest.fixture(scope="session")
def raw_frames(frames):
    """Raw tables as the derived-table code reads them: transformed, upserted
    into a scratch database (which collapses rows repeated across days), and
    read back — the production path."""
    from datetime import datetime, timezone

    from portfolio.load.db import make_engine
    from portfolio.load.models import Base
    from portfolio.load.read import read_frames
    from portfolio.load.upsert import upsert_rows
    from portfolio.transform import RAW_TABLE_ORDER, transform_all

    rows = transform_all(frames, ingested_at=datetime(2026, 10, 1, tzinfo=timezone.utc), base_currency="SGD")
    eng = make_engine("sqlite://")
    with eng.begin() as conn:
        for name in RAW_TABLE_ORDER:
            upsert_rows(conn, Base.metadata.tables[name], rows[name])
    return read_frames(eng, [*RAW_TABLE_ORDER, "benchmark_prices"])


@pytest.fixture()
def engine():
    from portfolio.load.models import Base

    # StaticPool: one shared connection so the in-memory DB survives reconnects
    eng = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(eng)
    return eng
