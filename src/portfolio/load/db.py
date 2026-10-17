"""The one place an engine is made: SQLite in WAL mode, tables created."""
from __future__ import annotations

from sqlalchemy import Engine, create_engine, event

from portfolio.load.models import Base


def make_engine(url: str) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        # WAL: the app keeps reading while a scheduled ingest writes
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    Base.metadata.create_all(engine)  # new tables appear; existing ones are left as is
    return engine
