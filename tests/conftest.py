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
def stmt(fixture_xml_path):
    from portfolio.flex.parse import parse_statement

    return parse_statement(fixture_xml_path)


@pytest.fixture(scope="session")
def frames(stmt):
    from portfolio.flex.frames import to_frames

    return to_frames(stmt)


@pytest.fixture(scope="session")
def raw_frames(frames):
    """Raw-table DataFrames as marts consume them (transform output shape)."""
    from datetime import datetime, timezone

    import pandas as pd

    from portfolio.transform import transform_all

    rows = transform_all(
        frames,
        ingested_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
        base_currency="SGD",
    )
    out = {name: pd.DataFrame(table_rows) for name, table_rows in rows.items()}
    out["benchmark_prices"] = pd.DataFrame()
    return out


@pytest.fixture()
def engine():
    from portfolio.load.models import Base

    # StaticPool: one shared connection so the in-memory DB survives reconnects
    eng = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(eng)
    return eng
